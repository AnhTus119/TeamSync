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


FALLBACK_MODELS = ('gemini-2.5-flash', 'gemini-flash-latest', 'gemini-2.0-flash')


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
    return 'error', f'Gemini báo lỗi {r.status_code}' + (f': {msg}' if msg else '')


def gemini(prompt):
    key = (current_app.config.get('GEMINI_API_KEY') or '').strip().strip('"').strip("'")
    if not key:
        raise AIUnavailable('no-key')
    configured = (current_app.config.get('GEMINI_MODEL') or '').strip()
    models = list(dict.fromkeys([m for m in (configured, *FALLBACK_MODELS) if m]))
    body = {'contents': [{'role': 'user', 'parts': [{'text': prompt}]}],
            'generationConfig': {'temperature': 0.4, 'responseMimeType': 'application/json'}}
    last = ('error', '')
    for model in models:
        try:
            r = requests.post(GEMINI_URL.format(model=model), headers={'x-goog-api-key': key, 'Content-Type': 'application/json'},
                              json=body, timeout=25)
        except requests.RequestException as e:
            log.warning('Gemini request failed: %s', type(e).__name__)
            raise AIUnavailable('error', 'Không kết nối được tới Gemini (kiểm tra mạng / tường lửa).')
        if r.status_code == 404:  # model name not available for this key: try the next one
            last = ('error', f'Không tìm thấy model {model}.')
            continue
        if r.status_code == 429:
            raise AIUnavailable('quota')
        if r.status_code >= 400:
            reason, detail = google_error(r)
            log.warning('Gemini %s: %s', r.status_code, detail)
            raise AIUnavailable(reason, detail)
        try:
            text = r.json()['candidates'][0]['content']['parts'][0]['text']
            return json.loads(text.strip().removeprefix('```json').removeprefix('```').removesuffix('```'))
        except Exception:
            raise AIUnavailable('invalid')
    raise AIUnavailable(*last)


NOTICE = {'quota': 'Gemini đã hết lượt miễn phí, kế hoạch được tạo theo quy tắc.',
          'error': 'Không gọi được Gemini, kế hoạch được tạo theo quy tắc.',
          'key': 'Không gọi được Gemini, kế hoạch được tạo theo quy tắc.',
          'invalid': 'Gemini trả kết quả không hợp lệ, kế hoạch được tạo theo quy tắc.'}


def run(ai, rules):
    """Try AI first, fall back to rules; returns (items, source, notice)."""
    try:
        items = ai()
        if items:
            return items, 'gemini', ''
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
    start, end = plan_window(a, tz)
    prompt = f"""Bạn là trợ lý lập kế hoạch cho nhóm sinh viên làm bài tập lớn. Trả lời bằng tiếng Việt, CHỈ trả JSON.
Đề bài: {a.title}
Mô tả đề bài: {(a.brief or '')[:3000]}
Ngày bắt đầu: {start.isoformat()}  Hạn cuối của các công việc: {end.isoformat()}
Thành viên (id, tên, vai trò, khối lượng đang mở): {json.dumps(members, ensure_ascii=False)}
Công việc đã có (không lặp lại): {json.dumps(existing[:60], ensure_ascii=False)}
Ghi chú của trưởng nhóm: {note or '(không có)'}
Yêu cầu: chia thành các giai đoạn hợp lý, tối đa {MAX_TASKS} công việc cụ thể, chia đều khối lượng (ưu tiên người đang ít việc),
hạn tăng dần theo giai đoạn, nằm trong khoảng ngày trên. Định dạng:
{{"tasks":[{{"phase":"tên giai đoạn","title":"tên công việc ngắn","description":"đầu ra cần bàn giao","responsible_id":<id thành viên>,"due_date":"YYYY-MM-DD","points":1|2|3|5,"priority":"low|medium|high"}}]}}"""
    data = gemini(prompt)
    ids = {m['id'] for m in members}
    taken = {x.strip().lower() for x in existing}
    out = []
    for x in (data.get('tasks') if isinstance(data, dict) else None) or []:
        if not isinstance(x, dict):
            continue
        title = str(x.get('title') or '').strip()[:200]
        due = parse_day(x.get('due_date'))
        rid = x.get('responsible_id')
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


def rule_schedule(lo, hi, work, busy):
    per_day = {}
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
            title, cat = f'Làm: {w["title"]}', 'study'
            note = f'Hoàn thành trước hạn {due.strftime("%d/%m")} để còn thời gian rà soát và nộp.'
        elif w['kind'] == 'review':
            start = end = lo if per_day.get(lo, 0) < 2 else min(lo + timedelta(days=1), hi)
            title, cat, note = f'Duyệt bài: {w["title"]}', 'review', 'Bài nộp đang chờ bạn duyệt.'
        elif w['kind'] == 'peer':
            start = end = min(max(lo, due - timedelta(days=1)), hi)
            title, cat, note = f'Đánh giá chéo: {w["title"]}', 'review', 'Phiếu đánh giá chéo đóng sau 7 ngày kể từ khi công việc hoàn thành.'
        elif w['kind'] == 'final':
            end = min(max(lo, due - timedelta(days=1)), hi)
            start = max(lo, end - timedelta(days=2))
            title, cat, note = f'Chuẩn bị nộp bài: {w["title"]}', 'deadline', f'Rà soát sản phẩm và báo cáo nhóm trước hạn nộp {due.strftime("%d/%m")}.'
        else:
            start = end = min(due, hi)
            title, cat, note = f'Rà soát tiến độ tuần: {w["title"]}', 'meeting', 'Cập nhật việc đã xong, việc trễ và phân công tuần tới.'
        if start > hi or end < lo:
            continue
        for i in range((end - start).days + 1):
            d = start + timedelta(days=i)
            per_day[d] = per_day.get(d, 0) + 1
        out.append({'title': title[:200], 'category': cat, 'start': start.isoformat(), 'end': end.isoformat(),
                    'note': note, 'project_id': w['project_id'], 'project_name': w['project_name']})
    return out


def ai_schedule(lo, hi, work, busy, note, projects):
    prompt = f"""Bạn là trợ lý sắp lịch học tập cho một sinh viên. Trả lời bằng tiếng Việt, CHỈ trả JSON.
Chỉ xếp lịch trong khoảng từ {lo.isoformat()} tới {hi.isoformat()}.
Việc cần làm (kind: task=công việc được giao, review=bài chờ duyệt, peer=phiếu đánh giá chéo, final=hạn nộp đề bài, weekly=gợi ý rà soát tuần; due=hạn): {json.dumps(work, ensure_ascii=False)}
Lịch đã có (tránh trùng, tránh quá tải): {json.dumps(busy, ensure_ascii=False)}
Mong muốn của sinh viên: {note or '(không có)'}
Yêu cầu: tối đa {MAX_ITEMS} mục, mỗi mục kết thúc trước hạn của việc đó, mỗi ngày không quá 2 mục, thêm mục tự học/ôn tập nếu sinh viên yêu cầu.
category thuộc {EDITABLE}. project_id lấy từ việc tương ứng hoặc null. Định dạng:
{{"items":[{{"title":"...","category":"study","start":"YYYY-MM-DD","end":"YYYY-MM-DD","note":"...","project_id":<id hoặc null>}}]}}"""
    data = gemini(prompt)
    names = {p['id']: p['name'] for p in projects}
    out = []
    for x in (data.get('items') if isinstance(data, dict) else None) or []:
        if not isinstance(x, dict):
            continue
        title = str(x.get('title') or '').strip()[:200]
        s, e = parse_day(x.get('start')), parse_day(x.get('end') or x.get('start'))
        if not title or not s or not e:
            continue
        s, e = max(s, lo), min(e, hi)
        if e < s or (e - s).days >= 60:
            continue
        pid = x.get('project_id') if x.get('project_id') in names else None
        out.append({'title': title, 'category': x.get('category') if x.get('category') in EDITABLE else 'study',
                    'start': s.isoformat(), 'end': e.isoformat(), 'note': str(x.get('note') or '').strip()[:2000],
                    'project_id': pid, 'project_name': names.get(pid, '')})
        if len(out) >= MAX_ITEMS:
            break
    out.sort(key=lambda x: x['start'])
    return out


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
        return {'items': items, 'source': source, 'notice': notice, 'members': members,
                'assignment_due_at': iso(a.due_at), 'ai_enabled': bool(current_app.config.get('GEMINI_API_KEY'))}

    @bp.post('/ai-schedule')
    @command()
    def ai_schedule_route():
        need(current_user().role != 'admin', 'FORBIDDEN', 'Tài khoản quản trị không dùng lịch học tập', 403)
        b = json_body()
        tz, note = tz_of(b), note_of(b)
        uid = current_user().id
        today, lo, hi = window_of(b, tz)
        work, busy = personal_context(uid, tz, lo, hi)
        projects = []
        for pid in sorted(my_project_ids(uid)):
            p = db.session.get(Project, pid)
            if p and p.status != 'archived':
                projects.append({'id': p.id, 'name': p.name})
        items, source, notice = run(lambda: ai_schedule(lo, hi, work, busy, note, projects), lambda: rule_schedule(lo, hi, work, busy))
        # Never propose an entry the user already has in this window (same title).
        mine = ScheduleItem.query.filter(ScheduleItem.owner_id == uid, ScheduleItem.end_date >= lo, ScheduleItem.start_date <= hi).all()
        taken = {y.title.strip().lower() for y in mine}
        items = [x for x in items if x['title'].strip().lower() not in taken][:MAX_ITEMS]
        if not items and not notice:
            notice = f'Không có việc mới cần xếp từ {lo.strftime("%d/%m")} đến {hi.strftime("%d/%m")}.'
        return {'items': items, 'source': source, 'notice': notice, 'from': lo.isoformat(), 'to': hi.isoformat(),
                'ai_enabled': bool(current_app.config.get('GEMINI_API_KEY'))}
