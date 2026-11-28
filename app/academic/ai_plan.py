"""AI hỗ trợ tạo timeline.

- POST /workflow/projects/<pid>/ai-plan (trưởng nhóm): đề xuất các giai đoạn/công việc có hạn và
  người làm từ đề bài, hạn nộp và thành viên. Chỉ trả đề xuất; tạo task do người dùng xác nhận
  qua API tạo công việc thông thường (vẫn qua mọi kiểm tra nghiệp vụ).
- POST /workflow/ai-schedule (mọi người dùng học tập): sắp lịch làm việc cá nhân từ task được giao,
  bài chờ duyệt, phiếu đánh giá chéo đang chờ và mô tả tự do. Lưu thành mục lịch khi người dùng xác nhận.

Nguồn: Google Gemini khi có GEMINI_API_KEY (gói miễn phí); không có key, hết lượt hoặc lỗi thì dùng
bộ sinh theo quy tắc nên luôn có kết quả. Đầu ra AI được kiểm tra chặt trước khi trả về.
"""
import json
import logging
import re
import threading
import time as time_module
from datetime import date, datetime, time, timedelta, timezone
import requests
from flask import current_app
from .core import *
from .schedule import EDITABLE, CATEGORIES, my_project_ids
from ..models.workflow import ScheduleItem, TaskPeerReview

log = logging.getLogger(__name__)
GEMINI_URL = 'https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent'
POINTS = (1, 2, 3, 5)
PRIORITY = ('low', 'medium', 'high')
MAX_TASKS = 15
MAX_ITEMS = 20
HORIZON = 28


class AIUnavailable(Exception):
    def __init__(self, reason, detail=''):
        super().__init__(reason)
        self.reason, self.detail = reason, detail


# ---------------------------------------------------------------- helpers
def tz_of(body):
    """Client offset in minutes (JS getTimezoneOffset: UTC − local). Default Việt Nam (UTC+7)."""
    try:
        off = int(body.get('tz_offset', -420))
    except (TypeError, ValueError):
        off = -420
    off = max(-840, min(840, off))
    return timezone(timedelta(minutes=-off))


def local_today(tz):
    return now().astimezone(tz).date()


def end_of_day(d, tz):
    """23:00 local time of day d, in UTC."""
    return datetime.combine(d, time(23, 0), tzinfo=tz).astimezone(timezone.utc)


def parse_day(v):
    try:
        return date.fromisoformat(str(v)[:10])
    except (TypeError, ValueError):
        return None


def note_of(body):
    v = body.get('note') or ''
    need(isinstance(v, str) and len(v) <= 1000, message='Mô tả tối đa 1000 ký tự')
    return v.strip()


FALLBACK_MODELS = ('gemini-2.5-flash', 'gemini-2.5-flash-lite', 'gemini-flash-latest', 'gemini-flash-lite-latest')


def google_error(r):
    """Short human reason from a Gemini error response (never contains the key)."""
    try:
        e = r.json().get('error', {})
        msg, status = str(e.get('message') or '')[:200], e.get('status') or ''
    except Exception:
        msg, status = '', ''
    if r.status_code in (400, 401, 403) and ('API key' in msg or status in ('UNAUTHENTICATED', 'PERMISSION_DENIED') or 'API_KEY' in msg):
        return 'key', 'API key không hợp lệ hoặc chưa bật Gemini API cho key này. Tạo lại key tại aistudio.google.com/apikey (key thường bắt đầu bằng “AIza”).'
    if r.status_code == 400 and 'location' in msg.lower():
        return 'error', 'Gemini chưa hỗ trợ khu vực mạng hiện tại.'
    return 'error', f'lỗi {r.status_code}' + (f': {msg}' if msg else '')


OVERLOADED = (500, 502, 503, 504)
RANK = {'busy': 3, 'quota': 3, 'key': 4, 'error': 2, 'invalid': 1}


def better(a, b):
    """Keep the most useful reason when several models failed (overloaded beats 'model not found')."""
    return b if RANK.get(b[0], 0) >= RANK.get(a[0], 0) else a


def post_json(name, url, headers, body, read_timeout):
    try:
        return requests.post(url, headers=headers, json=body, timeout=(15, read_timeout))
    except requests.ConnectTimeout as e:
        log.warning('%s request failed: %s', name, type(e).__name__)
        raise AIUnavailable('error', 'không mở được kết nối trong 15 giây (mạng / tường lửa / proxy)')
    except requests.Timeout as e:
        log.warning('%s request failed: %s', name, type(e).__name__)
        raise AIUnavailable('error', f'phản hồi quá lâu (quá {read_timeout} giây)')
    except requests.RequestException as e:
        log.warning('%s request failed: %s', name, type(e).__name__)
        raise AIUnavailable('error', f'không kết nối được ({type(e).__name__})')


def parse_json_text(text):
    """JSON from a model answer: drops <think>…</think> blocks and ``` fences, takes the outer {...}."""
    text = re.sub(r'<think>.*?</think>', '', text or '', flags=re.S).strip()
    text = text.removeprefix('```json').removeprefix('```').removesuffix('```').strip()
    if not text.startswith('{'):
        a, b = text.find('{'), text.rfind('}')
        text = text[a:b + 1] if a >= 0 and b > a else text
    return json.loads(text)


def config_key(name):
    return (current_app.config.get(name) or '').strip().strip('"').strip("'")


def gemini_call(prompt, read_timeout=60, max_tokens=2048):
    key = config_key('GEMINI_API_KEY')
    if not key:
        raise AIUnavailable('no-key')
    configured = (current_app.config.get('GEMINI_MODEL') or '').strip()
    models = list(dict.fromkeys([m for m in (configured, *FALLBACK_MODELS) if m]))
    last = ('error', '')
    for model in models:
        config = {'temperature': 0.3, 'responseMimeType': 'application/json', 'maxOutputTokens': max_tokens}
        if '2.5' in model and 'pro' not in model:
            config['thinkingConfig'] = {'thinkingBudget': 0}  # no "thinking" step: answers in seconds instead of ~30 s
        body = {'contents': [{'role': 'user', 'parts': [{'text': prompt}]}], 'generationConfig': config}
        for wait in (0, 3):  # overloaded (503): wait and retry once, then try the next model
            if wait:
                time_module.sleep(wait)
            r = post_json('Gemini', GEMINI_URL.format(model=model), {'x-goog-api-key': key, 'Content-Type': 'application/json'}, body, read_timeout)
            if r.status_code not in OVERLOADED:
                break
            last = better(last, ('busy', 'đang quá tải (503 phía Google)'))
        else:
            continue  # still overloaded: next model
        if r.status_code == 404:  # model not available for this key: try the next one
            last = better(last, ('error', f'không có model {model}'))
            continue
        if r.status_code == 429:
            last = better(last, ('quota', 'hết lượt miễn phí'))
            continue
        if r.status_code >= 400:
            reason, detail = google_error(r)
            log.warning('Gemini %s: %s', r.status_code, detail)
            raise AIUnavailable(reason, detail)
        try:
            return parse_json_text(r.json()['candidates'][0]['content']['parts'][0]['text'])
        except Exception:
            last = better(last, ('invalid', 'trả kết quả không đọc được'))
    raise AIUnavailable(*last)


# OpenAI-compatible providers. Model names change often, so the free / available models are read from the
# provider's own list (cached 1 hour) unless a model is set in .env. Qwen is preferred when it is offered.
PREFER = ('qwen', 'deepseek', 'llama-3.3', 'llama', 'gpt-oss', 'gemma', 'mistral', 'nemotron')
SKIP = re.compile(r'whisper|tts|guard|embed|audio|lyria|vision-only|1\.7b|nano|distil|playai|orpheus', re.I)
_model_cache = {}


def ranked(ids):
    def score(i):
        low = i.lower()
        return next((k for k, p in enumerate(PREFER) if p in low), len(PREFER))
    return sorted((i for i in ids if not SKIP.search(i)), key=score)


def openrouter_models(key):
    hit = _model_cache.get('openrouter')
    if hit and time_module.time() - hit[0] < 3600:
        return hit[1]
    try:
        r = requests.get('https://openrouter.ai/api/v1/models', headers={'Authorization': f'Bearer {key}'}, timeout=15)
        free = [m['id'] for m in r.json().get('data', [])
                if str(m.get('pricing', {}).get('prompt')) == '0' and str(m.get('pricing', {}).get('completion')) == '0' and m['id'] != 'openrouter/free']
    except Exception:
        free = []
    models = ranked(free)[:3] + ['openrouter/free']  # 'openrouter/free' = OpenRouter picks any free model
    _model_cache['openrouter'] = (time_module.time(), models)
    return models


def groq_models(key):
    hit = _model_cache.get('groq')
    if hit and time_module.time() - hit[0] < 3600:
        return hit[1]
    try:
        r = requests.get('https://api.groq.com/openai/v1/models', headers={'Authorization': f'Bearer {key}'}, timeout=15)
        ids = [m['id'] for m in r.json().get('data', []) if m.get('active', True)]
    except Exception:
        ids = []
    models = ranked(ids)[:3] or ['qwen/qwen3-32b', 'llama-3.3-70b-versatile']
    _model_cache['groq'] = (time_module.time(), models)
    return models


def openai_call(name, base, key, models, prompt, read_timeout, max_tokens):
    last = ('error', '')
    headers = {'Authorization': f'Bearer {key}', 'Content-Type': 'application/json'}
    if name == 'OpenRouter':
        headers.update({'HTTP-Referer': 'http://localhost', 'X-Title': 'TeamSync'})
    for model in models:
        body = {'model': model, 'temperature': 0.3, 'max_tokens': max_tokens, 'response_format': {'type': 'json_object'},
                'messages': [{'role': 'system', 'content': 'Bạn là trợ lý lập lịch. Chỉ trả về một đối tượng JSON hợp lệ, không giải thích.'},
                             {'role': 'user', 'content': prompt}]}
        for wait in (0, 3):
            if wait:
                time_module.sleep(wait)
            r = post_json(name, f'{base}/chat/completions', headers, body, read_timeout)
            if r.status_code == 400 and 'response_format' in body:  # some models do not support JSON mode
                body.pop('response_format')
                r = post_json(name, f'{base}/chat/completions', headers, body, read_timeout)
            if r.status_code not in OVERLOADED:
                break
            last = better(last, ('busy', 'đang quá tải'))
        else:
            continue
        if r.status_code in (401, 403):
            raise AIUnavailable('key', 'API key không hợp lệ')
        if r.status_code == 429:
            last = better(last, ('quota', 'hết lượt miễn phí / quá nhiều yêu cầu'))
            continue
        if r.status_code >= 400:
            last = better(last, ('error', f'không dùng được model {model} (lỗi {r.status_code})'))
            continue
        try:
            return parse_json_text(r.json()['choices'][0]['message']['content'])
        except Exception:
            last = better(last, ('invalid', 'trả kết quả không đọc được'))
    raise AIUnavailable(*last)


def providers():
    out = []
    if config_key('GEMINI_API_KEY'):
        out.append(('gemini', 'Gemini', lambda p, t, m: gemini_call(p, t, m)))
    if config_key('GROQ_API_KEY'):
        key = config_key('GROQ_API_KEY')
        out.append(('groq', 'Groq', lambda p, t, m: openai_call('Groq', 'https://api.groq.com/openai/v1', key,
                                                                [config_key('GROQ_MODEL')] if config_key('GROQ_MODEL') else groq_models(key), p, t, m)))
    if config_key('OPENROUTER_API_KEY'):
        key = config_key('OPENROUTER_API_KEY')
        out.append(('openrouter', 'OpenRouter', lambda p, t, m: openai_call('OpenRouter', 'https://openrouter.ai/api/v1', key,
                                                                            [config_key('OPENROUTER_MODEL')] if config_key('OPENROUTER_MODEL') else openrouter_models(key), p, t, m)))
    return out


def ai_enabled():
    return bool(providers())


_used = threading.local()


def gemini(prompt, read_timeout=60, max_tokens=2048):
    """Ask the configured AI services in order (Gemini → Groq → OpenRouter); first valid answer wins."""
    ps = providers()
    if not ps:
        raise AIUnavailable('no-key')
    reasons = []
    for key, label, call in ps:
        try:
            data = call(prompt, read_timeout, max_tokens)
            _used.provider = (key, label)
            return data
        except AIUnavailable as e:
            if e.reason != 'no-key':
                reasons.append(f'{label}: {e.detail or NOTICE_SHORT.get(e.reason, e.reason)}')
    raise AIUnavailable('error', '; '.join(reasons) or 'không có dịch vụ AI nào trả lời')


NOTICE_SHORT = {'quota': 'hết lượt miễn phí', 'busy': 'đang quá tải', 'invalid': 'trả kết quả không đọc được', 'error': 'lỗi', 'key': 'API key không hợp lệ'}
NOTICE = {'quota': 'AI hết lượt miễn phí, kế hoạch được tạo theo quy tắc.',
          'error': 'Không gọi được AI, kế hoạch được tạo theo quy tắc.',
          'key': 'Không gọi được AI, kế hoạch được tạo theo quy tắc.',
          'busy': 'Không gọi được AI, kế hoạch được tạo theo quy tắc.',
          'invalid': 'AI trả kết quả không hợp lệ, kế hoạch được tạo theo quy tắc.'}
LABELS = {'gemini': 'Gemini', 'groq': 'Groq', 'openrouter': 'OpenRouter', 'rules': 'quy tắc'}


def run(ai, rules):
    """Try AI first, fall back to rules; returns (items, source, notice). source = 'gemini' | 'groq' | 'openrouter' | 'rules'."""
    _used.provider = None
    try:
        items = ai()
        if items:
            return items, (_used.provider or ('gemini', 'Gemini'))[0], ''
        reason = 'invalid'
    except AIUnavailable as e:
        reason = e.reason
        if e.detail:
            return rules(), 'rules', f'{NOTICE.get(reason, "")} Lý do: {e.detail}'
    return rules(), 'rules', NOTICE.get(reason, '')


# ---------------------------------------------------------------- group plan
PHASES = [
    ('Khởi động', 0.12, [('Phân tích yêu cầu đề bài và chốt phạm vi', 'Danh sách chức năng/hạng mục bắt buộc, phạm vi và tiêu chí hoàn thành đã thống nhất.', 2, 'high', 'leader')]),
    ('Thiết kế', 0.30, [('Thiết kế giải pháp tổng thể', 'Sơ đồ kiến trúc / quy trình và phân chia hạng mục cho từng thành viên.', 3, 'high', None),
                        ('Thiết kế giao diện và dữ liệu', 'Bản phác thảo giao diện hoặc mô hình dữ liệu dùng cho phần thực hiện.', 2, 'medium', None)]),
    ('Thực hiện', 0.70, [('Thực hiện hạng mục {k}', 'Sản phẩm của hạng mục {k} theo thiết kế, kèm hướng dẫn kiểm tra.', 5, 'high', 'each')]),
    ('Kiểm thử & hoàn thiện', 0.85, [('Kiểm thử tích hợp và sửa lỗi', 'Biên bản kiểm thử các luồng chính và danh sách lỗi đã sửa.', 3, 'medium', None)]),
    ('Báo cáo & thuyết trình', 1.00, [('Viết báo cáo tổng kết', 'Báo cáo nhóm theo cấu trúc đề bài, có minh chứng đóng góp.', 3, 'medium', None),
                                      ('Chuẩn bị slide và thuyết trình', 'Slide trình bày và phân công phần nói của từng thành viên.', 2, 'low', None)]),
]


def plan_context(p):
    a = get(Assignment, p.assignment_id)
    ms = AssignmentMembership.query.filter_by(project_id=p.id, status='active').order_by(AssignmentMembership.id).all()
    load = {m.user_id: 0 for m in ms}
    for t in Task.query.filter(Task.project_id == p.id, Task.status.in_(['todo', 'in_progress', 'review'])):
        for x in TaskParticipant.query.filter_by(task_id=t.id, role='responsible'):
            if x.user_id in load:
                load[x.user_id] += t.points or 1
    members = [{'id': m.user_id, 'name': user_brief(m.user_id)['full_name'], 'role': m.role, 'open_points': load[m.user_id]} for m in ms]
    existing = [t.title for t in Task.query.filter_by(project_id=p.id).order_by(Task.id)]
    return a, members, existing


def plan_window(a, tz):
    start = local_today(tz)
    last = a.due_at.astimezone(tz).date()
    end = last - timedelta(days=1) if (last - start).days > 3 else last
    return start, max(end, start)


def rule_plan(p, a, members, existing, tz):
    start, end = plan_window(a, tz)
    span = max(1, (end - start).days)
    taken = {x.strip().lower() for x in existing}
    order = sorted(members, key=lambda m: (m['open_points'], m['role'] != 'leader', m['id']))
    leader = next((m for m in members if m['role'] == 'leader'), order[0])
    out, k, turn = [], 0, 0
    for phase, weight, templates in PHASES:
        due = start + timedelta(days=max(1, round(span * weight)))
        due = min(due, end)
        for title, desc, pts, prio, who in templates:
            people = members if who == 'each' else [None]
            for person in people:
                if who == 'each':
                    k += 1
                    resp = person
                elif who == 'leader':
                    resp = leader
                else:
                    resp = order[turn % len(order)]
                    turn += 1
                t = title.format(k=k)
                if t.lower() in taken:
                    continue
                out.append({'phase': phase, 'title': t, 'description': desc.format(k=k), 'responsible_id': resp['id'],
                            'due_at': iso(min(end_of_day(due, tz), a.due_at)), 'points': pts, 'priority': prio})
    return out


def ai_plan(p, a, members, existing, note, tz):
    """Compact prompt: members are numbered 1..n; Gemini answers with the number, we map it back."""
    start, end = plan_window(a, tz)
    people = '\n'.join(f"{i} {m['name']}{' (trưởng nhóm)' if m['role'] == 'leader' else ''}, đang mở {m['open_points']} điểm"
                       for i, m in enumerate(members, 1))
    prompt = f"""Lập kế hoạch bài tập lớn cho nhóm sinh viên. CHỈ trả JSON, tiếng Việt, ngắn gọn.
Đề: {a.title}. {(a.brief or '')[:1200]}
Từ {start.isoformat()} đến {end.isoformat()}. Thành viên (số thứ tự):
{people}
Đã có, không lặp: {'; '.join(x[:60] for x in existing[:30]) or 'không'}
Ghi chú: {note or 'không'}
Tối đa {MAX_TASKS} việc, chia đều (ưu tiên người ít việc), hạn tăng dần theo giai đoạn.
{{"tasks":[{{"phase":"giai đoạn","title":"tên việc","description":"đầu ra","m":<số thành viên>,"due_date":"YYYY-MM-DD","points":1|2|3|5,"priority":"low|medium|high"}}]}}"""
    data = gemini(prompt)
    ids = {m['id'] for m in members}
    taken = {x.strip().lower() for x in existing}
    out = []
    for x in (data.get('tasks') if isinstance(data, dict) else None) or []:
        if not isinstance(x, dict):
            continue
        title = str(x.get('title') or '').strip()[:200]
        due = parse_day(x.get('due_date'))
        n = x.get('m')
        rid = members[n - 1]['id'] if isinstance(n, int) and 1 <= n <= len(members) else x.get('responsible_id')
        if not title or title.lower() in taken or rid not in ids or not due:
            continue
        due = min(max(due, start), end)
        pts = x.get('points') if x.get('points') in POINTS else 2
        prio = x.get('priority') if x.get('priority') in PRIORITY else 'medium'
        out.append({'phase': str(x.get('phase') or 'Kế hoạch').strip()[:80], 'title': title,
                    'description': str(x.get('description') or '').strip()[:2000] or f'Sản phẩm bàn giao cho: {title}',
                    'responsible_id': rid, 'due_at': iso(min(end_of_day(due, tz), a.due_at)), 'points': pts, 'priority': prio})
        taken.add(title.lower())
        if len(out) >= MAX_TASKS:
            break
    out.sort(key=lambda x: x['due_at'])
    return out


# ---------------------------------------------------------------- personal schedule
def window_of(body, tz):
    """Planning window = the date range shown on the Timeline (never before today), max 60 days."""
    today = local_today(tz)
    lo = parse_day(body.get('from')) or today
    hi = parse_day(body.get('to')) or lo + timedelta(days=HORIZON - 1)
    lo = max(lo, today)
    hi = min(max(hi, lo), lo + timedelta(days=59))
    return today, lo, hi


def personal_context(uid, tz, lo, hi):
    """Work of the user that falls in [lo, hi]: assigned tasks, reviews waiting for them, pending peer
    reviews, course deadlines, and a weekly progress check per active project."""
    from .evidence import queue_data
    from .task_review import is_open, workers, reviewers, closes_at
    today = local_today(tz)
    pids = my_project_ids(uid)
    work = []
    rows = (Task.query.join(TaskParticipant, TaskParticipant.task_id == Task.id)
            .filter(TaskParticipant.user_id == uid, Task.status.in_(['todo', 'in_progress'])).order_by(Task.due_at).all())
    for t in rows:
        p = db.session.get(Project, t.project_id)
        due = t.due_at.astimezone(tz).date()
        if p and p.id in pids and p.status == 'active' and membership(p.id, uid) and due >= lo:
            work.append({'kind': 'task', 'title': t.title, 'project_id': p.id, 'project_name': p.name, 'points': t.points or 1, 'due': due.isoformat()})
    if lo <= today + timedelta(days=2):
        for r in queue_data()['to_review']:
            work.append({'kind': 'review', 'title': r['task_title'], 'project_id': r['project_id'], 'project_name': r['project_name'],
                         'points': 1, 'due': (today + timedelta(days=2)).isoformat()})
    for pid in pids:
        p = db.session.get(Project, pid)
        if not p or p.status != 'active' or not membership(pid, uid):
            continue
        for t in Task.query.filter_by(project_id=pid, status='done'):
            if is_open(t) and uid not in workers(t) and uid in reviewers(t) and \
                    TaskPeerReview.query.filter_by(task_id=t.id, reviewer_id=uid).count() < len(workers(t)):
                due = closes_at(t).astimezone(tz).date() - timedelta(days=1)
                if due >= lo:
                    work.append({'kind': 'peer', 'title': t.title, 'project_id': pid, 'project_name': p.name, 'points': 1, 'due': due.isoformat()})
        a = db.session.get(Assignment, p.assignment_id)
        if a and a.due_at:
            due = a.due_at.astimezone(tz).date()
            if lo <= due <= hi + timedelta(days=3):
                work.append({'kind': 'final', 'title': a.title, 'project_id': pid, 'project_name': p.name, 'points': 3, 'due': due.isoformat()})
            last_week = min(hi, due)
        else:
            last_week = hi
        d = lo + timedelta(days=(4 - lo.weekday()) % 7)  # Fridays in the window
        while d <= last_week:
            work.append({'kind': 'weekly', 'title': p.name, 'project_id': pid, 'project_name': p.name, 'points': 1, 'due': d.isoformat()})
            d += timedelta(days=7)
    busy = [{'title': x.title, 'start': x.start_date.isoformat(), 'end': x.end_date.isoformat()}
            for x in ScheduleItem.query.filter(ScheduleItem.owner_id == uid, ScheduleItem.end_date >= lo, ScheduleItem.start_date <= hi)]
    return work, busy


def describe(w):
    """Title, category and note of a planned block for one numbered piece of work (used by rules and Gemini)."""
    due = date.fromisoformat(w['due'])
    if w['kind'] == 'task':
        return f'Làm: {w["title"]}', 'study', f'Hoàn thành trước hạn {due.strftime("%d/%m")} để còn thời gian rà soát và nộp.'
    if w['kind'] == 'review':
        return f'Duyệt bài: {w["title"]}', 'review', 'Bài nộp đang chờ bạn duyệt.'
    if w['kind'] == 'peer':
        return f'Đánh giá chéo: {w["title"]}', 'review', 'Phiếu đánh giá chéo đóng sau 7 ngày kể từ khi công việc hoàn thành.'
    if w['kind'] == 'final':
        return f'Chuẩn bị nộp bài: {w["title"]}', 'deadline', f'Rà soát sản phẩm và báo cáo nhóm trước hạn nộp {due.strftime("%d/%m")}.'
    return f'Rà soát tiến độ tuần: {w["title"]}', 'meeting', 'Cập nhật việc đã xong, việc trễ và phân công tuần tới.'


def block(w, start, end):
    title, cat, note = describe(w)
    return {'title': title[:200], 'category': cat, 'start': start.isoformat(), 'end': end.isoformat(),
            'note': note, 'project_id': w['project_id'], 'project_name': w['project_name'], '_due': w['due']}


# ---------------------------------------------------------------- wishes in the note ("không xếp ngày 2/12", "bận thứ 3")
WEEKDAYS = {'2': 0, 'hai': 0, '3': 1, 'ba': 1, '4': 2, 'tư': 2, 'tu': 2, '5': 3, 'năm': 3, 'nam': 3, '6': 4, 'sáu': 4, 'sau': 4,
            '7': 5, 'bảy': 5, 'bay': 5}
NEG = re.compile(r'không|khong|tránh|tranh|bận|ban |nghỉ|nghi |trừ|tru |đừng|dung ', re.I)
ADD = re.compile(r'\b(ôn|on thi|học|hoc|thêm|them|luyện|luyen|đọc|doc|chuẩn bị|chuan bi|làm thêm|lam them)\b', re.I)


def in_window(day, month, lo, hi, year=None):
    for y in ([year] if year else [lo.year, lo.year + 1]):
        try:
            d = date(y, month, day)
        except ValueError:
            continue
        if lo - timedelta(days=31) <= d <= hi + timedelta(days=31):
            return d
    return None


def blocked_days(note, lo, hi):
    """Days the user asked to keep free, read from the note (dates d/m, ranges d/m–d/m, weekdays, 'cuối tuần')."""
    if not note or not NEG.search(note):
        return set()
    out = set()
    text = note.lower()
    dm = r'(\d{1,2})\s*[/\-.]\s*(\d{1,2})(?:\s*[/\-.]\s*(\d{2,4}))?'
    for m in re.finditer(dm + r'\s*(?:-|–|đến|den|tới|toi)\s*' + dm, text):
        a = in_window(int(m[1]), int(m[2]), lo, hi, int(m[3]) % 100 + 2000 if m[3] else None)
        b = in_window(int(m[4]), int(m[5]), lo, hi, int(m[6]) % 100 + 2000 if m[6] else None)
        if a and b and a <= b and (b - a).days <= 62:
            out |= {a + timedelta(days=i) for i in range((b - a).days + 1)}
        text = text.replace(m[0], ' ')
    for m in re.finditer(dm, text):
        d = in_window(int(m[1]), int(m[2]), lo, hi, int(m[3]) % 100 + 2000 if m[3] else None)
        if d:
            out.add(d)
    days = set()
    for m in re.finditer(r'thứ\s*(2|3|4|5|6|7|hai|ba|tư|tu|năm|nam|sáu|sau|bảy|bay)\b|thu\s*(2|3|4|5|6|7)\b', text):
        days.add(WEEKDAYS[m[1] or m[2]])
    if re.search(r'chủ nhật|chu nhat|\bcn\b', text):
        days.add(6)
    if re.search(r'cuối tuần|cuoi tuan', text):
        days |= {5, 6}
    d = lo
    while d <= hi:
        if d.weekday() in days:
            out.add(d)
        d += timedelta(days=1)
    return {d for d in out if lo <= d <= hi}


def avoid(items, blocked, lo, hi):
    """Move every entry off the days the user keeps free (earlier first, then later up to its deadline); drop if impossible."""
    if not blocked:
        return items
    out = []
    for i in items:
        s, e = date.fromisoformat(i['start']), date.fromisoformat(i['end'])
        last = min(hi, date.fromisoformat(i.get('_due') or hi.isoformat()))
        span = (e - s).days
        free = lambda a: all(a + timedelta(days=k) not in blocked for k in range(span + 1))
        if not free(s):
            earlier = [s - timedelta(days=k) for k in range(1, 15)]
            later = [s + timedelta(days=k) for k in range(1, 15)]
            ok = lambda a: lo <= a and a + timedelta(days=span) <= hi and free(a)
            # earlier first; later only while it still ends by its deadline
            s = next((a for a in earlier if ok(a)), None) or next((a for a in later if ok(a) and a + timedelta(days=span) <= last), None)
            if s is None:
                continue
            e = s + timedelta(days=span)
        out.append({**i, 'start': s.isoformat(), 'end': e.isoformat()})
    return out


def rule_schedule(lo, hi, work, busy, blocked=frozenset()):
    per_day = {d: 99 for d in blocked}
    for b in busy:
        s, e = date.fromisoformat(b['start']), date.fromisoformat(b['end'])
        for i in range((e - s).days + 1):
            per_day[s + timedelta(days=i)] = per_day.get(s + timedelta(days=i), 0) + 1
    out = []
    span_for = {1: 1, 2: 2, 3: 2, 5: 3}
    order = {'review': 0, 'peer': 1, 'task': 2, 'final': 3, 'weekly': 4}
    for w in sorted(work, key=lambda w: (w['due'], order[w['kind']])):
        due = date.fromisoformat(w['due'])
        if w['kind'] == 'task':
            end = min(max(lo, due - timedelta(days=1)), hi)
            length = span_for.get(w['points'], 2)
            start = max(lo, end - timedelta(days=length - 1))
            # At most two planned blocks per day: move earlier when the days are full.
            while start > lo and any(per_day.get(start + timedelta(days=i), 0) >= 2 for i in range((end - start).days + 1)):
                start -= timedelta(days=1)
                end -= timedelta(days=1)
        elif w['kind'] == 'review':
            start = end = lo if per_day.get(lo, 0) < 2 else min(lo + timedelta(days=1), hi)
        elif w['kind'] == 'peer':
            start = end = min(max(lo, due - timedelta(days=1)), hi)
        elif w['kind'] == 'final':
            end = min(max(lo, due - timedelta(days=1)), hi)
            start = max(lo, end - timedelta(days=2))
        else:
            start = end = min(due, hi)
        if start > hi or end < lo:
            continue
        for i in range((end - start).days + 1):
            d = start + timedelta(days=i)
            per_day[d] = per_day.get(d, 0) + 1
        out.append(block(w, start, end))
    return out


KIND = {'task': 'việc được giao', 'review': 'duyệt bài', 'peer': 'đánh giá chéo', 'final': 'chuẩn bị nộp đề bài', 'weekly': 'rà soát tuần'}


def ai_schedule(lo, hi, work, busy, note, projects, read_timeout=60, blocked=frozenset()):
    """Compact prompt: only numbered work (kind, size, due) and busy-day counts are sent; Gemini returns
    [number, start, end] and the entries are rebuilt here (titles, projects and notes never leave the server)."""
    lines = '\n'.join(f"{i}|{KIND[w['kind']]}|KL {w['points']}|hạn {w['due'][5:]}" for i, w in enumerate(work, 1))
    allow_new = bool(note and ADD.search(note))
    load = {}
    for b in busy:
        s, e = date.fromisoformat(b['start']), date.fromisoformat(b['end'])
        for k in range((e - s).days + 1):
            d = s + timedelta(days=k)
            if lo <= d <= hi:
                load[d] = load.get(d, 0) + 1
    busy_text = ', '.join(f'{d.strftime("%m-%d")}:{n}' for d, n in sorted(load.items())) or 'không'
    prompt = f"""Sắp lịch học cho sinh viên trong {lo.isoformat()}..{hi.isoformat()}. CHỈ trả JSON.
Việc (số|loại|khối lượng|hạn MM-DD):
{lines or '(không có)'}
Ngày đã bận (MM-DD:số mục): {busy_text}
TUYỆT ĐỐI không xếp vào các ngày: {', '.join(d.strftime('%m-%d') for d in sorted(blocked)) or 'không có'}
Mong muốn: {note or 'không'}
Xếp MỌI việc trong danh sách, mỗi việc 1 khoảng ngày kết thúc trước hoặc đúng hạn, mỗi ngày tối đa 2 mục.
{('"them": việc mới theo mong muốn (ví dụ ôn thi), tối đa 5.' if allow_new else '"them" luôn để [] (không thêm việc ngoài danh sách).')}
{{"x":[[số,"YYYY-MM-DD","YYYY-MM-DD"]],"them":[["tên ngắn","YYYY-MM-DD","YYYY-MM-DD"]]}}"""
    data = gemini(prompt, read_timeout, max_tokens=1024)
    if not isinstance(data, dict):
        return []
    out, seen = [], set()
    for row in data.get('x') or []:
        if not (isinstance(row, list) and len(row) >= 2 and isinstance(row[0], int) and 1 <= row[0] <= len(work)) or row[0] in seen:
            continue
        w = work[row[0] - 1]
        s, e = parse_day(row[1]), parse_day(row[2] if len(row) > 2 else row[1])
        if not s or not e:
            continue
        last = min(hi, date.fromisoformat(w['due']))
        s, e = max(s, lo), min(e, last)
        if e < s:
            continue
        seen.add(row[0])
        out.append(block(w, s, e))
    for row in (data.get('them') or [])[:5] if allow_new else []:
        if not (isinstance(row, list) and len(row) >= 2 and isinstance(row[0], str) and row[0].strip()):
            continue
        s, e = parse_day(row[1]), parse_day(row[2] if len(row) > 2 else row[1])
        if not s or not e:
            continue
        s, e = max(s, lo), min(e, hi)
        if e < s:
            continue
        out.append({'title': row[0].strip()[:100], 'category': 'study', 'start': s.isoformat(), 'end': e.isoformat(),
                    'note': 'Theo mong muốn bạn nhập khi sắp lịch.', 'project_id': None, 'project_name': ''})
        if len(out) >= MAX_ITEMS:
            break
    out.sort(key=lambda x: x['start'])
    return out[:MAX_ITEMS]


# ---------------------------------------------------------------- background jobs (AI sắp lịch chạy nền)
# The request only gathers the user's data; the slow part (Gemini, up to JOB_READ_TIMEOUT seconds) runs in a
# thread that then saves the entries itself, so the user can leave the dialog and keep working.
import threading
import uuid
JOB_READ_TIMEOUT = 180
JOBS = {}
_jobs_lock = threading.Lock()


def schedule_inputs(uid, body):
    tz, note = tz_of(body), note_of(body)
    today, lo, hi = window_of(body, tz)
    work, _ = personal_context(uid, tz, lo, hi)
    # Entries made by an earlier AI run (and not edited by hand) inside the window are re-arranged by this run.
    rows = ScheduleItem.query.filter(ScheduleItem.owner_id == uid, ScheduleItem.end_date >= lo, ScheduleItem.start_date <= hi).all()
    replace = [x.id for x in rows if x.source == 'ai' and x.start_date >= lo]
    busy = [{'title': x.title, 'start': x.start_date.isoformat(), 'end': x.end_date.isoformat()} for x in rows if x.id not in replace]
    projects = []
    for pid in sorted(my_project_ids(uid)):
        p = db.session.get(Project, pid)
        if p and p.status != 'archived':
            projects.append({'id': p.id, 'name': p.name})
    return {'note': note, 'lo': lo, 'hi': hi, 'work': work, 'busy': busy, 'projects': projects, 'replace': replace,
            'blocked': blocked_days(note, lo, hi)}


def plan_schedule(uid, x, read_timeout=60):
    blocked = x.get('blocked') or set()
    items, source, notice = run(lambda: ai_schedule(x['lo'], x['hi'], x['work'], x['busy'], x['note'], x['projects'], read_timeout, blocked),
                                lambda: rule_schedule(x['lo'], x['hi'], x['work'], x['busy'], blocked))
    items = avoid(items, blocked, x['lo'], x['hi'])  # enforced here whatever Gemini answered
    # Never propose an entry the user already has (made by hand) in this window (same title).
    mine = ScheduleItem.query.filter(ScheduleItem.owner_id == uid, ScheduleItem.end_date >= x['lo'], ScheduleItem.start_date <= x['hi']).all()
    taken = {y.title.strip().lower() for y in mine if y.id not in set(x.get('replace') or [])}
    items = [{k: v for k, v in i.items() if k != '_due'} for i in items if i['title'].strip().lower() not in taken][:MAX_ITEMS]
    if not items and not notice:
        notice = f'Không có việc mới cần xếp từ {x["lo"].strftime("%d/%m")} đến {x["hi"].strftime("%d/%m")}.'
    return items, source, notice


def run_job(app, job_id, uid, x):
    with app.app_context():
        job = JOBS[job_id]
        try:
            items, source, notice = plan_schedule(uid, x, JOB_READ_TIMEOUT)
            allowed = {p['id'] for p in x['projects']}
            ids, payloads, removed = [], [], []
            if items:  # re-arrange: the earlier AI entries of this window give way to the new plan
                for old in ScheduleItem.query.filter(ScheduleItem.id.in_(x['replace'] or [0]), ScheduleItem.owner_id == uid, ScheduleItem.source == 'ai'):
                    removed.append({'title': old.title, 'category': old.category, 'start': old.start_date.isoformat(), 'end': old.end_date.isoformat(),
                                    'note': old.note, 'project_id': old.project_id, 'source': 'ai'})
                    db.session.delete(old)
            for i in items:
                pid = i['project_id'] if i['project_id'] in allowed else None
                row = ScheduleItem(owner_id=uid, project_id=pid, title=i['title'][:200], note=(i.get('note') or '')[:2000],
                                   category=i['category'] if i['category'] in EDITABLE else 'study',
                                   start_date=date.fromisoformat(i['start']), end_date=date.fromisoformat(i['end']), source='ai')
                db.session.add(row)
                db.session.flush()
                ids.append(row.id)
                payloads.append({'title': row.title, 'category': row.category, 'start': i['start'], 'end': i['end'], 'note': row.note,
                                 'project_id': pid, 'source': 'ai'})
            blocked = sorted(d.strftime('%d/%m') for d in x.get('blocked') or [])
            from .notifications import push
            span = f'{x["lo"].strftime("%d/%m")} – {x["hi"].strftime("%d/%m")}'
            push('ai.schedule', [uid], 'AI đã sắp xong lịch' if ids else 'AI sắp lịch: không có lịch mới',
                 (f'Đã thêm {len(ids)} mục cho {span} ({LABELS.get(source, "AI")} sắp)' + (f', thay {len(removed)} mục AI cũ' if removed else '') if ids else (notice or f'Không có việc mới cần xếp cho {span}'))
                 + (f' · đã tránh {", ".join(blocked)}' if blocked else ''), f'/timeline?view=created&from={x["lo"].isoformat()}')
            db.session.commit()
            job.update(status='done', ids=ids, payloads=payloads, removed=removed, blocked=blocked, source=source, source_label=LABELS.get(source, 'AI'), notice=notice,
                       finished_at=iso(now()))
        except Exception as e:  # keep the user informed; nothing half-saved
            db.session.rollback()
            log.exception('AI schedule job failed')
            job.update(status='failed', error='Không tạo được lịch AI. Thử lại sau.', finished_at=iso(now()))
            try:
                from .notifications import push
                push('ai.schedule', [uid], 'AI sắp lịch thất bại', 'Không tạo được lịch AI. Thử lại sau.', '/timeline')
                db.session.commit()
            except Exception:
                db.session.rollback()
        finally:
            db.session.remove()


def job_dto(job):
    return {k: v for k, v in job.items() if k != 'uid'}


# ---------------------------------------------------------------- routes
def register(bp):
    @bp.post('/projects/<int:pid>/ai-plan')
    @command()
    def ai_plan_route(pid):
        p = project(pid, manage=True)
        state(p, ['active'])
        b = json_body()
        tz, note = tz_of(b), note_of(b)
        a, members, existing = plan_context(p)
        need(members, message='Nhóm chưa có thành viên')
        need(a.due_at > now(), message='Đề bài đã hết hạn, không lập kế hoạch mới')
        items, source, notice = run(lambda: ai_plan(p, a, members, existing, note, tz),
                                    lambda: rule_plan(p, a, members, existing, tz))
        return {'items': items, 'source': source, 'source_label': LABELS.get(source, 'AI'), 'notice': notice, 'members': members,
                'assignment_due_at': iso(a.due_at), 'ai_enabled': ai_enabled()}

    @bp.post('/ai-schedule')
    @command()
    def ai_schedule_route():
        """Synchronous proposal (no saving); kept for scripts and tests."""
        need(current_user().role != 'admin', 'FORBIDDEN', 'Tài khoản quản trị không dùng lịch học tập', 403)
        uid = current_user().id
        x = schedule_inputs(uid, json_body())
        items, source, notice = plan_schedule(uid, x)
        return {'items': items, 'source': source, 'source_label': LABELS.get(source, 'AI'), 'notice': notice, 'from': x['lo'].isoformat(), 'to': x['hi'].isoformat(),
                'ai_enabled': ai_enabled()}

    @bp.post('/ai-schedule/jobs')
    @command()
    def ai_schedule_job_start():
        """Start AI sắp lịch in the background; the entries are saved when it finishes."""
        need(current_user().role != 'admin', 'FORBIDDEN', 'Tài khoản quản trị không dùng lịch học tập', 403)
        uid = current_user().id
        with _jobs_lock:
            need(not any(j['uid'] == uid and j['status'] == 'running' for j in JOBS.values()), 'JOB_RUNNING', 'AI đang sắp lịch cho bạn, chờ xong rồi thử lại', 409)
        x = schedule_inputs(uid, json_body())
        job_id = uuid.uuid4().hex
        JOBS[job_id] = {'id': job_id, 'uid': uid, 'status': 'running', 'from': x['lo'].isoformat(), 'to': x['hi'].isoformat(),
                        'ai_enabled': ai_enabled(), 'started_at': iso(now())}
        threading.Thread(target=run_job, args=(current_app._get_current_object(), job_id, uid, x), daemon=True).start()
        return job_dto(JOBS[job_id]), 202

    @bp.get('/ai-jobs/<job_id>')
    @command()
    def ai_job(job_id):
        job = JOBS.get(job_id)
        need(job and job['uid'] == current_user().id, 'NOT_FOUND', 'Không tìm thấy tác vụ AI (máy chủ có thể đã khởi động lại)', 404)
        return job_dto(job)
