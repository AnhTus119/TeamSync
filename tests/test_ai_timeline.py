"""AI hỗ trợ tạo timeline (rule fallback without key, Gemini output validation) and Timeline milestones."""
from unittest import mock
from test_workflow import app, template, Client, demo, uid, MA, TH, QB, GV, COORD


def test_ai_plan_rules_without_key_and_only_leader(app):
    d = demo(app)
    leader, member = Client(app, MA), Client(app, QB)
    member.req(f'/workflow/projects/{d["pid"]}/ai-plan', {}, code=403)
    r = leader.req(f'/workflow/projects/{d["pid"]}/ai-plan', {'note': 'Ưu tiên giao diện', 'tz_offset': -420})
    assert r['source'] == 'rules' and not r['ai_enabled'] and r['items']
    member_ids = {m['id'] for m in r['members']}
    p = leader.req(f'/projects/{d["pid"]}')
    existing = {t['title'].lower() for t in leader.req(f'/projects/{d["pid"]}/tasks?page_size=100')['items']}
    dues = [x['due_at'] for x in r['items']]
    assert dues == sorted(dues) and all(x <= p['assignment']['due_at'] for x in dues)
    for x in r['items']:
        assert x['responsible_id'] in member_ids and x['points'] in (1, 2, 3, 5) and x['priority'] in ('low', 'medium', 'high')
        assert x['title'].lower() not in existing and x['description']
    # a proposal is created through the normal task API (all business checks still apply)
    x = r['items'][0]
    t = leader.req(f'/projects/{d["pid"]}/tasks', {'title': x['title'], 'description': x['description'], 'due_at': x['due_at'], 'points': x['points'],
                                                  'priority': x['priority'], 'participants': [{'user_id': x['responsible_id'], 'role': 'responsible'}]}, code=201)
    again = leader.req(f'/workflow/projects/{d["pid"]}/ai-plan', {})
    assert all(i['title'] != t['title'] for i in again['items'])  # not proposed twice


def test_ai_plan_uses_gemini_and_validates_output(app):
    d = demo(app)
    app.config['GEMINI_API_KEY'] = 'test-key'
    ma = uid(app, MA)
    body = {'tasks': [
        {'phase': 'Thiết kế', 'title': 'Vẽ wireframe', 'description': 'Bộ wireframe 5 màn hình', 'responsible_id': ma, 'due_date': '2026-12-05', 'points': 3, 'priority': 'high'},
        {'phase': 'X', 'title': 'Người lạ', 'description': '', 'responsible_id': 999999, 'due_date': '2026-12-05', 'points': 3, 'priority': 'high'},  # not a member
        {'phase': 'X', 'title': 'Thiết kế màn hình đăng nhập', 'responsible_id': ma, 'due_date': '2026-12-05'},  # already exists
        {'phase': 'X', 'title': 'Hạn sai', 'responsible_id': ma, 'due_date': 'không phải ngày'}]}
    import json
    fake = mock.Mock(status_code=200)
    fake.json.return_value = {'candidates': [{'content': {'parts': [{'text': json.dumps(body)}]}}]}
    fake.raise_for_status.return_value = None
    with mock.patch('app.academic.ai_plan.requests.post', return_value=fake) as post:
        r = Client(app, MA).req(f'/workflow/projects/{d["pid"]}/ai-plan', {'tz_offset': -420})
    assert post.call_args.kwargs['headers']['x-goog-api-key'] == 'test-key'
    assert r['source'] == 'gemini' and [x['title'] for x in r['items']] == ['Vẽ wireframe']
    assert r['items'][0]['due_at'].startswith('2026-12-05T16:00')  # 23:00 Việt Nam
    # quota / network errors fall back to rules with a notice
    with mock.patch('app.academic.ai_plan.requests.post', return_value=mock.Mock(status_code=429)):
        r = Client(app, MA).req(f'/workflow/projects/{d["pid"]}/ai-plan', {})
    assert r['source'] == 'rules' and 'hết lượt' in r['notice'] and r['items']


def test_ai_schedule_rules_and_saving(app):
    c = Client(app, TH)
    r = c.req('/workflow/ai-schedule', {'tz_offset': -420})
    assert r['source'] == 'rules' and r['items']
    assert any(x['title'].startswith('Đánh giá chéo:') for x in r['items'])  # open per-task review waiting for Thu Hà
    for x in r['items']:
        assert x['start'] <= x['end'] and x['category'] in ('meeting', 'deadline', 'study', 'review', 'personal', 'other')
    x = r['items'][0]
    saved = c.req('/workflow/schedule', {k: x[k] for k in ('title', 'category', 'start', 'end', 'note', 'project_id')}, code=201)
    assert saved['editable'] and saved['title'] == x['title']
    Client(app, 'admin@teamsync.test').req('/workflow/ai-schedule', {}, code=403)


def test_timeline_milestones_and_staff_filters(app):
    d = demo(app)
    stu = Client(app, MA).req('/workflow/schedule?view=mine&from=2026-11-01&to=2027-01-31')
    teacher = Client(app, GV).req('/workflow/schedule?view=mine&from=2026-11-01&to=2027-01-31')
    ms = [x for x in teacher['items'] if x['kind'] == 'milestone']
    assert teacher['is_staff'] and teacher['courses'] and all(p['course_id'] for p in teacher['projects'])
    assert not [x for x in teacher['items'] if x['kind'] == 'task']  # teacher timeline: milestones + shared/own entries
    assert all(x['course_id'] == d['cid'] for x in ms)
    sm = {x['id'] for x in stu['items'] if x['kind'] == 'milestone'}
    assert {x['id'] for x in ms} <= sm and not stu['is_staff']  # same milestone ids for the student of that course


def test_staff_home_has_referrals_and_group_cards(app):
    home = Client(app, 'thuhang@gv.teamsync.test').req('/workflow/home')
    assert home['review_queue'] == len(home['review_rows']) >= 1
    g = home['courses'][0]['groups'][0]
    assert {'leader', 'member_names', 'done', 'total', 'late', 'help', 'pending_review', 'team_name'} <= set(g)
    assert g['member_names'][0] == g['leader']['full_name']
    assert 'review_rows' not in Client(app, MA).req('/workflow/home')
