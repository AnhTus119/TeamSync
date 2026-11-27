"""Regression tests: independent review, instructor referral, evidence criteria, import, dashboard."""
import io, sqlite3, shutil
from pathlib import Path
from datetime import timedelta
from flask_migrate import upgrade
from test_workflow import app, template, Client, now, demo, name_of, MA, TH, QB, GL, GV, GV_AI
from app import create_app
from app.extensions import db


def find_task(c, title):
    return next(t for t in c.req('/workflow/tasks')['items'] if t['title'] == title)


def submit(c, tid, note, evidence=None, url='https://example.com/ban-nop'):
    t = c.req(f'/tasks/{tid}')
    a = c.req(f'/tasks/{tid}/assets', {'url': url}, code=201)
    links = [{'criterion_id': cid, 'asset_id': a['id']} for cid in (evidence or [])]
    return c.req(f'/tasks/{tid}/submissions', {'version': t['version'], 'description': note, 'asset_ids': [a['id']], 'evidence_links': links}, code=201), a


def test_full_referral_flow_and_history(app):
    ma, th, gv = (Client(app, e) for e in (MA, TH, GV_AI))
    t = find_task(ma, 'Cập nhật ước tính đầu việc tích hợp')  # ChatbotAI: Thu Hà leads, Minh Anh responsible
    proj = ma.req(f'/projects/{t["project_id"]}')
    aid = proj['assignment_id']
    # another ChatbotAI member who is neither leader nor in the roster of this submission
    qb = Client(app, next(m['user']['email'] for m in proj['members'] if m['role'] != 'leader' and m['user']['email'] != MA))
    crit = gv.req(f'/workflow/assignments/{aid}/evidence-criteria', {'title': 'Bảng ước tính tích hợp'}, code=201)
    ma.req(f'/workflow/assignments/{aid}/evidence-criteria', {'title': 'Sinh viên tạo'}, code=403)
    first = ma.req(f'/tasks/{t["id"]}')['submissions'][0]
    s, asset = submit(ma, t['id'], 'Lần 2 có bảng ước tính', [crit['id']])
    assert s['attempt_no'] == 2
    detail = ma.req(f'/tasks/{t["id"]}')
    latest = detail['submissions'][-1]
    assert latest['evidence'][0]['criterion_title'] == 'Bảng ước tính tích hợp' and latest['evidence'][0]['asset']['id'] == asset['id']
    assert not latest['can_review'] and 'có tên' in latest['review_block_reason']
    ma.req(f'/submissions/{s["id"]}/review', {'version': detail['version'], 'action': 'accept'}, code=403)
    # instructor cannot decide before the leader refers this exact submission
    gv.req(f'/submissions/{s["id"]}/review', {'version': detail['version'], 'action': 'accept'}, code=403)
    qb.req(f'/submissions/{s["id"]}/refer', {'reason': 'Nhờ thầy xem'}, code=403)  # not leader
    th.req(f'/submissions/{s["id"]}/refer', {'reason': ''}, code=400)
    th.req(f'/submissions/{s["id"]}/refer', {'reason': 'Nhờ giảng viên kiểm tra cách ước tính'}, code=201)
    th.req(f'/submissions/{s["id"]}/refer', {'reason': 'Lặp'}, code=409)
    q = gv.req('/workflow/submissions')
    assert any(r['id'] == s['id'] and r['can_review'] for r in q['to_review'])
    v = gv.req(f'/tasks/{t["id"]}')['version']
    gv.req(f'/submissions/{s["id"]}/review', {'version': v, 'action': 'return', 'reason': ''}, code=400)
    gv.req(f'/submissions/{s["id"]}/review', {'version': v, 'action': 'return', 'reason': 'Bổ sung', 'repair_due_at': (now() - timedelta(hours=1)).isoformat()}, code=400)
    gv.req(f'/submissions/{s["id"]}/review', {'version': v, 'action': 'return', 'reason': 'Bổ sung', 'repair_due_at': (now() + timedelta(days=90)).isoformat()}, code=400)
    gv.req(f'/submissions/{s["id"]}/review', {'version': v, 'action': 'return', 'reason': 'Bổ sung phần xác thực', 'repair_due_at': (now() + timedelta(days=2)).isoformat()})
    # the second decision on the same submission is rejected with fresh-data message
    qb.req(f'/submissions/{s["id"]}/review', {'version': v + 1, 'action': 'accept'}, code=409)
    s3, _ = submit(ma, t['id'], 'Lần 3 đã bổ sung xác thực')
    v = qb.req(f'/tasks/{t["id"]}')['version']
    # old submission cannot receive a decision for the current one
    qb.req(f'/submissions/{s["id"]}/review', {'version': v, 'action': 'accept'}, code=409)
    gv.req(f'/submissions/{s3["id"]}/review', {'version': v, 'action': 'accept'}, code=403)  # referral was for attempt 2 only
    qb.req(f'/submissions/{s3["id"]}/review', {'version': v, 'action': 'accept'})
    final = ma.req(f'/tasks/{t["id"]}')
    assert final['status'] == 'done' and [x['status'] for x in final['submissions']] == ['returned', 'returned', 'accepted']
    assert final['submissions'][0]['id'] == first['id'] and final['submissions'][0]['review_reason'] == first['review_reason']
    assert final['submissions'][1]['referral']['reason'] == 'Nhờ giảng viên kiểm tra cách ước tính'
    assert final['submissions'][1]['link'] == f'/tasks/{t["id"]}?submission={s["id"]}#submission-{s["id"]}'
    rep = th.req(f'/workflow/projects/{t["project_id"]}/report')
    # latest attempt has no criterion link, so the criterion counts nothing; the hidden history still reads
    assert any(e['title'] == 'Bảng ước tính tích hợp' for e in rep['evidence'])


def test_leader_in_roster_must_be_reviewed_by_someone_else(app):
    ma, gl = Client(app, MA), Client(app, GL)
    t = find_task(ma, 'Nộp kịch bản kiểm thử luồng tiếp nhận')  # Free2do, MA leads and submitted
    d = ma.req(f'/tasks/{t["id"]}')
    sid = d['latest_submission_id']
    ma.req(f'/submissions/{sid}/review', {'version': d['version'], 'action': 'accept'}, code=403)
    assert d['submissions'][-1]['can_refer']
    assert any(r['id'] == sid for r in gl.req('/workflow/submissions')['to_review'])
    gl.req(f'/submissions/{sid}/review', {'version': d['version'], 'action': 'accept'})


def test_evidence_scope_and_hidden_criterion(app):
    ma, gv = Client(app, MA), Client(app, GV)
    t = find_task(ma, 'Sửa lỗi tạo phiếu hỗ trợ')  # Free2do (TS. Nguyễn Khánh An), in_progress
    p = ma.req(f'/projects/{t["project_id"]}')
    own = gv.req(f'/workflow/assignments/{p["assignment_id"]}/evidence-criteria', {'title': 'Báo cáo tuần'}, code=201)
    chatbot = find_task(ma, 'Cập nhật ước tính đầu việc tích hợp')
    foreign = ma.req(f'/workflow/assignments/{ma.req("/projects/" + str(chatbot["project_id"]))["assignment_id"]}/evidence-criteria')['items'][0]
    d = ma.req(f'/tasks/{t["id"]}')
    a = ma.req(f'/tasks/{t["id"]}/assets', {'url': 'https://example.com/a'}, code=201)
    b = ma.req(f'/tasks/{t["id"]}/assets', {'url': 'https://example.com/b'}, code=201)
    body = {'version': d['version'], 'description': 'Nộp', 'asset_ids': [a['id']]}
    ma.req(f'/tasks/{t["id"]}/submissions', {**body, 'evidence_links': [{'criterion_id': foreign['id'], 'asset_id': a['id']}]}, code=400)
    ma.req(f'/tasks/{t["id"]}/submissions', {**body, 'evidence_links': [{'criterion_id': own['id'], 'asset_id': b['id']}]}, code=400)
    hidden = gv.req(f'/workflow/evidence-criteria/{own["id"]}', {'version': own['version'], 'is_active': False}, 'PATCH')
    assert own['id'] not in [x['id'] for x in ma.req(f'/workflow/assignments/{p["assignment_id"]}/evidence-criteria')['items']]
    ma.req(f'/tasks/{t["id"]}/submissions', {**body, 'evidence_links': [{'criterion_id': own['id'], 'asset_id': a['id']}]}, code=409)
    gv.req(f'/workflow/evidence-criteria/{own["id"]}', {'version': hidden['version'], 'is_active': True}, 'PATCH')
    s = ma.req(f'/tasks/{t["id"]}/submissions', {**body, 'evidence_links': [{'criterion_id': own['id'], 'asset_id': a['id']}]}, code=201)
    staff_view = gv.req(f'/workflow/assignments/{p["assignment_id"]}/evidence-criteria')
    assert staff_view['can_manage'] and next(x for x in staff_view['items'] if x['id'] == own['id'])['is_active']
    rep = ma.req(f'/workflow/projects/{t["project_id"]}/report')
    assert next(e for e in rep['evidence'] if e['criterion_id'] == own['id'])['pending'] == 1
    assert s['attempt_no'] == 3


def test_outsider_and_instructor_boundaries(app):
    ma, sv1, gv1 = Client(app, MA), Client(app, demo(app)['outsider']), Client(app, GV_AI)  # outsider student, instructor of another course
    t = find_task(ma, 'Sửa lỗi tạo phiếu hỗ trợ')
    sid = ma.req(f'/tasks/{t["id"]}')['latest_submission_id']
    sv1.req(f'/tasks/{t["id"]}', code=404)
    sv1.req(f'/workflow/projects/{t["project_id"]}/report', code=404)
    sv1.req(f'/workflow/projects/{t["project_id"]}/export?format=xlsx', code=404)
    gv1.req(f'/tasks/{t["id"]}', code=404)  # instructor of another course
    gv1.req(f'/submissions/{sid}/refer', {'reason': 'x'}, code=404)
    assert all(r['project_id'] != t['project_id'] for r in sv1.req('/workflow/submissions')['mine'])
    r = ma.c.get(f'/api/v1/workflow/projects/{t["project_id"]}/export?format=xlsx')
    assert r.status_code == 200 and r.data[:2] == b'PK'
    from openpyxl import load_workbook
    wb = load_workbook(io.BytesIO(r.data))
    assert 'Minh chứng' in wb.sheetnames


def test_import_preview_error_then_fixed_file(app):
    gv = Client(app, GV)
    cid = next(c['id'] for c in gv.req('/workflow/home')['courses'] if c['title'] == 'Phát triển ứng dụng Web')
    bad = 'student_code,full_name,email\nTSNEW041,An Bình,anbinh@example.org\nTSNEW042,Bảo Linh,email-khong-hop-le\n'
    r = gv.c.post(f'/api/v1/courses/{cid}/imports/preview', data={'file': (io.BytesIO(bad.encode()), 'ds.csv')}, headers={'X-CSRF-Token': gv.token})
    assert r.status_code == 201 and r.json['data']['counts'] == {'total': 2, 'errors': 1}
    batch = r.json['data']
    assert next(x for x in batch['rows'] if x['row_no'] == 3)['errors_json']
    gv.req(f'/imports/{batch["id"]}/commit', {'version': batch['version']}, code=409)
    good = bad.replace('email-khong-hop-le', 'baolinh@example.org')
    r = gv.c.post(f'/api/v1/courses/{cid}/imports/preview', data={'file': (io.BytesIO(good.encode()), 'ds.csv')}, headers={'X-CSRF-Token': gv.token})
    batch = r.json['data']
    assert batch['counts']['errors'] == 0
    gv.req(f'/imports/{batch["id"]}/commit', {'version': batch['version']})
    codes = {e['student_code'] for e in gv.req(f'/courses/{cid}/enrollments?page_size=100')['items']}
    assert {'TSNEW041', 'TSNEW042'} <= codes


def test_dashboard_counts_and_alerts(app):
    ma = Client(app, MA)
    d = ma.req('/workflow/home')
    s = d['stats']
    assert s['projects'] == 7 and s['lead'] == 2 and s['project_tasks'] == sum(p['total'] for p in d['projects'])
    assert s['task_total'] == len(ma.req('/workflow/tasks?scope=mine')['items'])  # same personal set as the Kanban board
    assert s['repair'] >= 1 and s['due'] >= 1 and s['review'] >= 1
    assert s['peer_score'] is not None and 0 < s['peer_score'] <= 10 and s['peer_projects'] >= 1
    assert d['review_queue'] == len(ma.req('/workflow/submissions')['to_review'])
    assert any(a['kind'] == 'repeat_return' and 'submission=' in a['link'] for a in d['alerts'])
    # stale review (>48h) is shown only to people allowed to review it
    gl = Client(app, GL)
    assert any(a['kind'] == 'stale_review' for a in gl.req('/workflow/home')['alerts'])
    can_review = {r['link'] for r in ma.req('/workflow/submissions')['to_review']}
    assert all(a['link'] in can_review for a in d['alerts'] if a['kind'] == 'stale_review')
    script = next(t for t in ma.req('/workflow/tasks')['items'] if t['title'] == 'Nộp kịch bản kiểm thử luồng tiếp nhận')
    assert not any(a['kind'] == 'stale_review' and a['task_id'] == script['id'] for a in d['alerts'])  # Minh Anh submitted it
    assert [t['due_at'] for t in d['upcoming']] == sorted(t['due_at'] for t in d['upcoming'])


def test_seed_is_repeat_safe_and_upgrade_keeps_old_rows(tmp_path):
    app = create_app({'TESTING': True, 'SQLALCHEMY_DATABASE_URI': 'sqlite:///' + str(tmp_path / 'db.sqlite'), 'PRIVATE_STORAGE': str(tmp_path / 'f'), 'DEMO_CLOCK_ENABLED': True})
    mig = str(Path(__file__).parents[1] / 'migrations')
    with app.app_context():
        upgrade(directory=mig, revision='d12220261122')
        con = db.engine.raw_connection()
        cols = [r[1] for r in con.execute('PRAGMA table_info(project)')]
        con.close()
        if 'team_name' in cols:  # baseline built from current models: emulate an old database
            with db.engine.begin() as cx:
                cx.exec_driver_sql('ALTER TABLE project DROP COLUMN team_name')
        with db.engine.begin() as cx:
            cx.exec_driver_sql("INSERT INTO user (email, full_name, password_hash, role, is_active, created_at) VALUES ('old@x.vn','Cũ','x','user',1,'2026-01-01')")
            uid = cx.exec_driver_sql("SELECT id FROM user WHERE email='old@x.vn'").scalar()
            cx.exec_driver_sql(f"INSERT INTO workspace (name, description, owner_id, created_at) VALUES ('W','',{uid},'2026-01-01')")
            wid = cx.exec_driver_sql("SELECT id FROM workspace WHERE name='W'").scalar()
            cx.exec_driver_sql(f"INSERT INTO project (workspace_id, name, description, created_by, created_at, mode, status, version) VALUES ({wid},'Dự án cũ','',{uid},'2026-01-01','legacy','active',1)")
        upgrade(directory=mig)
        with db.engine.begin() as cx:
            assert cx.exec_driver_sql("SELECT team_name FROM project WHERE name='Dự án cũ'").scalar() == ''
            for name in ('evidence_criterion', 'submission_evidence', 'submission_referral'):
                cx.exec_driver_sql(f'SELECT count(*) FROM {name}')
        from app.academic.workflow_seed import seed_demo
        from app.models import Project
        seed_demo()
        n = Project.query.count()
        p = Project.query.filter_by(team_name='Đội Hỗ trợ').one()
        p.team_name = 'Đội Hỗ trợ (đã sửa)'
        db.session.commit()
        seed_demo()
        assert Project.query.count() == n and db.session.get(Project, p.id).team_name == 'Đội Hỗ trợ (đã sửa)'
        db.engine.dispose()


def test_random_seed_keeps_business_rules(app):
    from app.academic.random_seed import seed_random
    from app.models import Task
    from app.models.academic import TaskSubmission, AssignmentMembership
    with app.app_context():
        r = seed_random(projects=4, tasks=10, seed=7)
        assert r['tasks'] > 0
        for t in Task.query.join(TaskSubmission, TaskSubmission.task_id == Task.id).distinct():
            subs = sorted(TaskSubmission.query.filter_by(task_id=t.id), key=lambda s: s.attempt_no)
            assert t.latest_submission_id == subs[-1].id
            expect = {'review': 'pending', 'done': 'accepted', 'in_progress': 'returned'}[t.status]
            assert subs[-1].status == expect and all(s.status == 'returned' for s in subs[:-1])
            for s in subs:
                if s.reviewed_by:
                    assert s.reviewed_by not in s.participant_ids and s.reviewed_by != s.submitted_by
    ma, gv = Client(app, MA), Client(app, GV)
    home = ma.req('/workflow/home')
    for t in ma.req('/workflow/tasks')['items'][:40]:
        ma.req(f'/tasks/{t["id"]}')
    q = gv.req('/workflow/submissions')
    assert home['stats']['project_tasks'] >= 28 and all(row['can_review'] for row in q['to_review'])


def test_personal_kanban_scope_excludes_review_only_tasks(app):
    gl = Client(app, GL)
    me_id = gl.req('/auth/me')['id']
    mine = gl.req('/workflow/tasks?scope=mine')['items']
    assert mine and all(any(p['user_id'] == me_id for p in t['participants']) for t in mine)
    review_ids = {r['task_id'] for r in gl.req('/workflow/submissions')['to_review']}
    assert review_ids and not review_ids & {t['id'] for t in mine}  # review-only work stays in Bài cần tôi duyệt
    assert {t['id'] for t in mine} <= {t['id'] for t in gl.req('/workflow/tasks')['items']}
    assert all(p['created_at'] for p in gl.req('/workflow/home')['projects'])


def test_schedule_owner_edit_share_and_scope(app):
    ma, th, sv1 = Client(app, MA), Client(app, TH), Client(app, demo(app)['outsider'])
    pid = next(p['id'] for p in ma.req('/workflow/home')['projects'] if p['name'] == 'Free2do')
    today = ma.req('/workflow/schedule?view=created')['today']
    ma.req('/workflow/schedule', {'title': 'Sai', 'category': 'study', 'start': today, 'end': '2000-01-01'}, code=400)
    ma.req('/workflow/schedule', {'title': 'Sai', 'category': 'task', 'start': today, 'end': today}, code=400)
    sv1.req('/workflow/schedule', {'title': 'Không thuộc nhóm', 'category': 'meeting', 'start': today, 'end': today, 'project_id': pid}, code=404)
    x = ma.req('/workflow/schedule', {'title': 'Họp chốt demo', 'category': 'meeting', 'start': today, 'end': today, 'project_id': pid, 'note': 'Phòng 201'}, code=201)
    shared = next(i for i in th.req('/workflow/schedule?view=mine')['items'] if i['kind'] == 'item' and i['id'] == x['id'])
    assert shared['editable'] is False and shared['owner_name'] == name_of(app, MA)
    assert all(i['id'] != x['id'] for i in sv1.req('/workflow/schedule?view=mine')['items'] if i['kind'] == 'item')
    th.req(f'/workflow/schedule/{x["id"]}', {'version': x['version'], 'title': 'Sửa hộ'}, 'PATCH', code=403)
    th.req(f'/workflow/schedule/{x["id"]}', None, 'DELETE', code=403)
    moved = ma.req(f'/workflow/schedule/{x["id"]}', {'version': x['version'], 'start': '2026-12-01', 'end': '2026-12-02', 'category': 'review'}, 'PATCH')
    assert (moved['start'], moved['end'], moved['category']) == ('2026-12-01', '2026-12-02', 'review')
    ma.req(f'/workflow/schedule/{x["id"]}', {'version': x['version'], 'title': 'Bản cũ'}, 'PATCH', code=409)
    mine = ma.req('/workflow/schedule?view=mine')
    tasks = [i for i in mine['items'] if i['kind'] == 'task']
    assert tasks and all(not i['editable'] for i in mine['items'])
    ma.req(f'/workflow/schedule/{x["id"]}', None, 'DELETE')
    assert all(i['id'] != x['id'] for i in ma.req('/workflow/schedule?view=created&from=2026-11-25')['items'])


def test_member_cards_code_and_published_score_only(app):
    d = demo(app); pid, aid = d['pid'], d['aid']
    gv1, sv1, sv2 = Client(app, GV), Client(app, MA), Client(app, TH)
    p = sv1.req(f'/projects/{pid}')
    assert all(m['student_code'] for m in p['members']) and all(m['peer_score'] is None for m in p['members'])
    r = gv1.req(f'/assignments/{aid}/evaluation-rounds', {'title': 'Đợt thử', 'closes_at': (now() + timedelta(days=2)).isoformat()}, code=201)
    target = next(m for m in p['members'] if m['user']['email'] == QB)
    sv2.req(f'/workflow/projects/{pid}/peer', {'round_id': r['id'], 'items': [{'reviewee_id': target['user_id'], 'attitude': 9, 'quality': 8}]}, method='PUT')
    assert next(m for m in sv1.req(f'/projects/{pid}')['members'] if m['user_id'] == target['user_id'])['peer_score'] is None  # round still open
    gv1.req(f'/evaluation-rounds/{r["id"]}/close', {'version': r['version']})
    m = next(m for m in sv1.req(f'/projects/{pid}')['members'] if m['user_id'] == target['user_id'])
    assert m['peer_score'] == 8.5 and 'reviewer_id' not in m
