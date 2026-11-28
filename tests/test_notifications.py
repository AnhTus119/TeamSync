"""Every important change reaches the people concerned as an in-app notification (not only deadline reminders)."""
from datetime import timedelta
from test_workflow import app, template, Client, demo, uid, now, MA, TH, QB, GL, GV
from app.extensions import db
from app.models.academic import Notification
from app.common.jobs import dispatch_outbox


def inbox(app, email, title):
    with app.app_context():
        dispatch_outbox()
        return [n for n in Notification.query.filter_by(recipient_id=uid(app, email)).order_by(Notification.id) if n.title == title]


def test_actions_notify_the_right_people(app):
    d = demo(app); pid = d['pid']
    ma, th, qb, gl, gv = (Client(app, e) for e in (MA, TH, QB, GL, GV))
    p = ma.req(f'/projects/{pid}')
    # leader assigns a task → the assignee is told; the leader (actor) is not
    t = ma.req(f'/projects/{pid}/tasks', {'title': 'Viết hướng dẫn cài đặt', 'description': 'Tệp README', 'due_at': (now() + timedelta(days=3)).isoformat(),
                                          'points': 2, 'priority': 'medium', 'participants': [{'user_id': uid(app, QB), 'role': 'responsible'}]}, code=201)
    n = inbox(app, QB, 'Bạn được giao công việc mới')
    assert n and 'Viết hướng dẫn cài đặt' in n[-1].body and n[-1].target_path == f'/tasks/{t["id"]}'
    assert not inbox(app, MA, 'Bạn được giao công việc mới')
    # task re-assigned / edited
    t = ma.req(f'/tasks/{t["id"]}')
    ma.req(f'/workflow/tasks/{t["id"]}/assignment', {'version': t['version'], 'title': 'Viết hướng dẫn cài đặt (sửa)', 'description': 'README + ảnh',
                                                      'points': 3, 'priority': 'high', 'participants': [{'user_id': uid(app, GL), 'role': 'responsible'}]})
    assert inbox(app, GL, 'Công việc được cập nhật')
    # extension request → leader; decision → requester
    t = gl.req(f'/tasks/{t["id"]}')
    x = gl.req(f'/tasks/{t["id"]}/extensions', {'version': t['version'], 'due_at': (now() + timedelta(days=5)).isoformat(), 'reason': 'Ốm 2 ngày'}, code=201)
    assert inbox(app, MA, 'Có đề nghị gia hạn')
    ma.req(f'/extensions/{x["id"]}/decide', {'version': x['version'], 'action': 'approve', 'reason': 'Đồng ý'})
    assert inbox(app, GL, 'Đề nghị gia hạn được đồng ý')
    # teacher changes the assignment deadline → students of the course
    a = gv.req(f'/assignments/{p["assignment_id"]}')
    gv.req(f'/assignments/{a["id"]}', {'version': a['version'], 'title': a['title'], 'brief': a['brief'], 'due_at': (now() + timedelta(days=50)).isoformat()}, method='PATCH')
    assert inbox(app, TH, 'Đề bài được cập nhật')
    # minutes and a shared timeline entry → other members
    th.req(f'/workflow/projects/{pid}/minutes', {'title': 'Họp tuần 3', 'notes': 'Chốt giao diện'}, code=201)
    assert inbox(app, QB, 'Biên bản họp mới')
    day = (now() + timedelta(days=2)).date().isoformat()
    th.req('/workflow/schedule', {'title': 'Họp online', 'category': 'meeting', 'start': day, 'end': day, 'project_id': pid}, code=201)
    assert inbox(app, GL, 'Lịch nhóm mới')
    # a task approved as done → members who did not work on it are invited to the peer review
    s = next(x for x in ma.req('/workflow/submissions')['to_review'] if x['project_id'] == pid)
    detail = th.req(f'/tasks/{s["task_id"]}')
    sub = next(x for x in detail['submissions'] if x['id'] == s['id'])
    ma.req(f'/submissions/{s["id"]}/review', {'version': detail['version'], 'action': 'accept', 'reason': 'Tốt'})
    others = [e for e in (TH, QB, GL) if uid(app, e) not in set(sub['participant_ids'] if 'participant_ids' in sub else []) | {sub.get('submitted_by')}]
    assert any(inbox(app, e, 'Mời đánh giá chéo') for e in others)


def test_new_leader_is_notified(app):
    d = demo(app); pid = d['pid']
    x = Client(app, MA).req(f'/workflow/projects/{pid}/departures', {'reason': 'Chuyển lớp'}, code=201)
    for e in (TH, QB):
        x = Client(app, e).req(f'/workflow/departures/{x["id"]}/vote', {'version': x['version'], 'agree': True})
    assert x['status'] == 'approved' and x['successor']
    who = next(e for e in (TH, QB, GL) if uid(app, e) == x['successor']['id'])
    assert inbox(app, who, 'Bạn trở thành trưởng nhóm')
    assert any(inbox(app, e, 'Nhóm có trưởng nhóm mới') for e in (TH, QB, GL) if e != who)
