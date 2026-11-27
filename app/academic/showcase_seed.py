"""TeamSync showcase demo: seven projects for Minh Anh's team and instructor Khánh An.

Runs once per database (RuntimeSetting 'teamsync_showcase_v1'); restarting the app
never overwrites data the user changed. Deadlines are relative to the first run.
"""
import hashlib
from datetime import timedelta
from werkzeug.security import generate_password_hash
from .core import *
from ..models import Workspace, WorkspaceMember, ProjectMember
from ..models.teamwork import MatrixReview, Meeting
from ..models.workflow import EvidenceCriterion, SubmissionEvidence, SubmissionReferral

KEY = 'teamsync_showcase_v1'

PEOPLE = [
    ('gv2@gmail.com', 'Giảng viên Khánh An', 'instructor'),
    ('minhanh@gmail.com', 'Minh Anh', 'user'),
    ('thuha@gmail.com', 'Thu Hà', 'user'),
    ('quocbao@gmail.com', 'Quốc Bảo', 'user'),
    ('gialinh@gmail.com', 'Gia Linh', 'user'),
    ('annhien@gmail.com', 'An Nhiên', 'user'),
]

# (project, team, leader, criteria, tasks)
# task: (title, status, responsible, collaborators, due_hours, points, submissions)
# submission: (status, submitted_by, reviewer, hours_ago, note, review_reason, criterion_index)
PROJECTS = [
    ('Free2do', 'Đội Hỗ trợ', 'MA', ['Kiểm thử luồng tạo phiếu hỗ trợ', 'Tài liệu hướng dẫn sử dụng'], [
        ('Gắn tag khẩn cho lỗi đồng bộ', 'todo', 'MA', [], -6, 2, []),
        ('Sửa lỗi tạo phiếu hỗ trợ', 'in_progress', 'MA', [], 20, 5, [
            ('returned', 'MA', 'GL', 30, 'Đã sửa lỗi lưu phiếu khi thiếu mô tả.', 'Phiếu vẫn mất tệp đính kèm khi tải lại trang.', 0),
            ('returned', 'MA', 'GL', 6, 'Đã giữ tệp đính kèm khi tải lại và bổ sung kiểm thử.', 'Cần kiểm thử thêm với khách chưa đăng nhập.', 0)]),
        ('Nộp kịch bản kiểm thử luồng tiếp nhận', 'review', 'MA', [], 30, 3, [
            ('pending', 'MA', None, 50, 'Kịch bản gồm 12 trường hợp tiếp nhận phiếu, kèm dữ liệu mẫu.', '', 0)]),
        ('Chuẩn hóa mẫu phản hồi khách hàng', 'done', 'MA', ['GL'], -70, 2, [
            ('accepted', 'GL', 'TH', 26, 'Bộ mẫu phản hồi đã thống nhất giọng văn.', 'Đạt yêu cầu.', 1)]),
    ]),
    ('ChatbotAI', 'Đội Atlas', 'TH', ['Bộ câu hỏi kiểm thử chatbot'], [
        ('Đặt lịch tổng duyệt Sprint Atlas', 'todo', 'QB', [], -14, 1, []),
        ('Chia backlog cho sprint tiếp theo', 'in_progress', 'TH', [], 40, 2, []),
        ('Cập nhật ước tính đầu việc tích hợp', 'in_progress', 'MA', [], 60, 2, [
            ('returned', 'MA', 'TH', 28, 'Bảng ước tính cho 8 đầu việc tích hợp.', 'Thiếu ước tính cho phần xác thực.', None)]),
        ('Kiểm thử câu trả lời mẫu', 'review', 'QB', [], 50, 3, [
            ('pending', 'QB', None, 3, 'Đã chạy 40 câu hỏi mẫu, ghi lại câu trả lời sai.', '', 0)]),
    ]),
    ('Dự án Quản lý công nghệ thông tin', 'Đội Tài liệu', 'QB', ['Đối chiếu phiên bản tài liệu'], [
        ('Đối chiếu mã SHA-256 của hồ sơ bàn giao', 'todo', 'MA', [], -9, 2, []),
        ('Rà soát quyền tải tài liệu nội bộ', 'in_progress', 'TH', [], 18, 2, []),
        ('Nộp báo cáo đối chiếu phiên bản', 'review', 'MA', [], 70, 3, [
            ('pending', 'MA', None, 5, 'Báo cáo đối chiếu 5 phiên bản tài liệu.', '', 0)]),
        ('Bổ sung minh chứng kiểm chứng tài liệu', 'in_progress', 'GL', [], 26, 1, []),
    ]),
    ('Không gian thành viên', 'Đội Thành viên', 'MA', [], [
        ('Xác nhận danh sách thành viên hoạt động', 'done', 'MA', [], -80, 1, [
            ('accepted', 'MA', 'QB', 31, 'Danh sách thành viên đã đối chiếu.', 'Đạt yêu cầu.', None)]),
        ('Mời nhóm QA vào dự án triển khai', 'todo', 'TH', [], -4, 1, []),
        ('Cập nhật hồ sơ vai trò', 'in_progress', 'QB', [], 90, 2, []),
        ('Kiểm tra quyền xem hồ sơ', 'todo', 'GL', [], 100, 2, []),
    ]),
    ('Lịch triển khai Release', 'Đội Phát hành', 'GL', [], [
        ('Chốt lịch phát hành với nhóm vận hành', 'todo', 'MA', [], -26, 2, []),
        ('Bàn giao danh sách rủi ro đã duyệt', 'done', 'TH', [], -60, 2, [
            ('accepted', 'TH', 'MA', 22, 'Danh sách 9 rủi ro kèm phương án.', 'Đạt yêu cầu.', None)]),
        ('Kiểm tra các mốc phát hành gấp', 'in_progress', 'QB', [], 12, 1, []),
        ('Chuẩn bị ghi chú phát hành', 'todo', 'GL', [], 120, 1, []),
    ]),
    ('Bảng điều hành dự án', 'Đội Tiến độ', 'QB', [], [
        ('Phân công người phụ trách báo cáo tuần', 'in_progress', 'MA', [], 16, 1, []),
        ('Nộp bản dựng dashboard', 'review', 'QB', [], 44, 3, [
            ('pending', 'QB', None, 23, 'Bản dựng dashboard có biểu đồ tiến độ.', '', None)]),
        ('Kiểm chứng số liệu bảng tiến độ', 'in_progress', 'MA', [], 80, 2, [
            ('returned', 'MA', 'QB', 27, 'Đối chiếu số liệu tuần 1–3.', 'Số liệu tuần 3 chưa khớp nguồn.', None)]),
        ('Thiết kế bộ lọc dữ liệu', 'todo', 'TH', [], 130, 2, []),
    ]),
    ('Cổng nghiệm thu bàn giao', 'Đội Nghiệm thu', 'TH', [], [
        ('Bàn giao hướng dẫn vận hành phiên bản mới', 'done', 'GL', [], -90, 2, [
            ('accepted', 'GL', 'TH', 35, 'Hướng dẫn vận hành 14 trang.', 'Đạt yêu cầu.', None)]),
        ('Kiểm tra tài liệu nghiệm thu trước khi ký', 'todo', 'MA', [], 22, 2, []),
        ('Tổng hợp biên bản nghiệm thu', 'in_progress', 'QB', [], 70, 1, []),
        ('Chuẩn hóa checklist nghiệm thu', 'todo', 'TH', [], 140, 1, []),
    ]),
]

KEYS = {'MA': 'minhanh@gmail.com', 'TH': 'thuha@gmail.com', 'QB': 'quocbao@gmail.com', 'GL': 'gialinh@gmail.com'}


def seed_showcase_projects():
    if db.session.get(RuntimeSetting, KEY):
        return False
    from ..common.storage import root
    password = generate_password_hash('12345')
    users = {}
    for email, name, role in PEOPLE:
        u = User.query.filter_by(email=email).first()
        if not u:
            u = User(email=email, full_name=name, role=role, password_hash=password)
            db.session.add(u)
            db.session.flush()
        users[email] = u
    teacher = users['gv2@gmail.com']
    who = {k: users[v] for k, v in KEYS.items()}
    at = now().replace(second=0, microsecond=0)
    naive = lambda d: d.replace(tzinfo=None)

    def event(action, etype, eid, pid, actor, when, reason=None, cid=None):
        db.session.add(AuditEvent(action=action, entity_type=etype, entity_id=eid, project_id=pid, course_id=cid,
                                  actor_id=actor.id, request_id='showcase', reason=reason, created_at=when))

    def stored(task, owner, name, content):
        key = hashlib.md5(f'showcase-{task.id}-{name}'.encode()).hexdigest()
        dest = root() / key
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(content)
        a = EvidenceAsset(task_id=task.id, uploaded_by=owner.id, kind='file', storage_key=key, original_filename=name,
                          mime_type='text/plain', sha256=hashlib.sha256(content).hexdigest(), size_bytes=len(content),
                          integrity_status='fixed_file')
        db.session.add(a)
        db.session.flush()
        return a

    for n, (pname, team, lead, crit_titles, tasks) in enumerate(PROJECTS, 1):
        code = f'TSD-{n:02}'
        if CourseOffering.query.filter_by(code=code, term='Demo TeamSync').first():
            continue
        w = Workspace(name=code, description=pname, owner_id=teacher.id)
        db.session.add(w)
        db.session.flush()
        c = CourseOffering(code=code, title=pname, term='Demo TeamSync', status='active', workspace_id=w.id, created_by=teacher.id)
        db.session.add(c)
        db.session.flush()
        roster = [teacher] + list(who.values()) + ([users['annhien@gmail.com']] if n == 1 else [])
        for i, u in enumerate(roster):
            db.session.add(WorkspaceMember(workspace_id=w.id, user_id=u.id, role='owner' if u == teacher else 'member'))
            db.session.add(CourseEnrollment(course_id=c.id, user_id=u.id, role='instructor' if u == teacher else 'student',
                                            student_code=None if u == teacher else f'TSDSV{i:02}'))
        a = Assignment(course_id=c.id, title=pname, brief=f'Dự án demo: {pname}.', status='active', is_hidden=False,
                       due_at=at + timedelta(days=25), group_min=3, group_max=10, group_mode='self',
                       formation_due_at=at + timedelta(days=5))
        db.session.add(a)
        db.session.flush()
        crits = []
        for title in crit_titles:
            cr = EvidenceCriterion(assignment_id=a.id, title=title, created_by=teacher.id)
            db.session.add(cr)
            db.session.flush()
            crits.append(cr)
        p = Project(name=pname, team_name=team, description=pname, workspace_id=w.id, created_by=who[lead].id,
                    assignment_id=a.id, mode='academic', status='active')
        db.session.add(p)
        db.session.flush()
        for k, u in who.items():
            role = 'leader' if k == lead else 'member'
            db.session.add(AssignmentMembership(assignment_id=a.id, project_id=p.id, user_id=u.id, role=role))
            db.session.add(ProjectMember(project_id=p.id, user_id=u.id, project_role='manager' if role == 'leader' else 'member'))
        event('group.assigned', 'project', p.id, p.id, who[lead], at - timedelta(days=14))
        for ti, (title, status, resp, collab, due_h, points, subs) in enumerate(tasks):
            due = at + timedelta(hours=due_h)
            created = at - timedelta(days=12, hours=ti)
            t = Task(project_id=p.id, title=title, description=f'Hoàn thành và bàn giao kết quả: {title}.', status=status,
                     priority='high' if due_h < 24 else 'medium', points=points, created_by=who[lead].id,
                     assignee_id=who[resp].id, primary_assignee_id=who[resp].id, due_at=due, original_due_at=due,
                     created_at=naive(created), updated_at=naive(created))
            db.session.add(t)
            db.session.flush()
            people = [who[resp]] + [who[x] for x in collab]
            for k, u in enumerate(people):
                db.session.add(TaskParticipant(task_id=t.id, user_id=u.id, role='responsible' if k == 0 else 'collaborator'))
            event('task.created', 'task', t.id, p.id, who[lead], created)
            if status != 'todo':
                event('task.started', 'task', t.id, p.id, who[resp], created + timedelta(hours=2))
            for si, (sstatus, by, reviewer, ago, note, review_reason, crit_index) in enumerate(subs, 1):
                received = at - timedelta(hours=ago)
                fname = 'bao-cao-kiem-thu.txt' if crit_index is not None else f'san-pham-lan-{si}.txt'
                asset = stored(t, who[by], fname, f'# {title}\n\nLần nộp {si}: {note}\n'.encode())
                rev = EvidenceRevision(task_id=t.id, revision_no=si, description=note, created_by=who[by].id, created_at=received)
                db.session.add(rev)
                db.session.flush()
                db.session.add(EvidenceRevisionAsset(revision_id=rev.id, asset_id=asset.id))
                sub_due = due if si == len(subs) else received + timedelta(hours=8)
                s = TaskSubmission(task_id=t.id, revision_id=rev.id, attempt_no=si, submitted_by=who[by].id,
                                   participant_ids=sorted(u.id for u in people), received_at=received,
                                   submitted_due_at=sub_due, status=sstatus, created_at=received,
                                   reviewed_by=who[reviewer].id if reviewer else None,
                                   reviewed_at=received + timedelta(hours=3) if reviewer else None,
                                   review_reason=review_reason or None)
                db.session.add(s)
                db.session.flush()
                if crit_index is not None and crit_index < len(crits):
                    db.session.add(SubmissionEvidence(submission_id=s.id, criterion_id=crits[crit_index].id, asset_id=asset.id))
                t.latest_submission_id = s.id
                event('task.submitted', 'task_submission', s.id, p.id, who[by], received)
                if reviewer:
                    event('submission.' + sstatus, 'task_submission', s.id, p.id, who[reviewer],
                          received + timedelta(hours=3), review_reason)
                if sstatus == 'accepted':
                    t.completed_at = naive(received + timedelta(hours=3))
            if pname == 'Dự án Quản lý công nghệ thông tin' and status == 'review':
                s = db.session.get(TaskSubmission, t.latest_submission_id)
                db.session.add(SubmissionReferral(submission_id=s.id, project_id=p.id, referred_by=who[lead].id,
                                                  instructor_id=teacher.id,
                                                  reason='Nhờ giảng viên xác nhận cách đối chiếu phiên bản tài liệu.'))
                event('submission.referred', 'task_submission', s.id, p.id, who[lead], at - timedelta(hours=4),
                      'Nhờ giảng viên xác nhận cách đối chiếu phiên bản tài liệu.')
                db.session.add(OutboxEvent(event_type='submission.referred', aggregate_id=s.id, payload={
                    'recipients': [teacher.id], 'subject': f'{t.title} · {pname} · Lần {s.attempt_no}',
                    'path': f'/tasks/{t.id}?submission={s.id}#submission-{s.id}'}))
        if n <= 4:
            r = PeerRound(assignment_id=a.id, title='Đánh giá giữa kỳ', opens_at=at - timedelta(days=10),
                          closes_at=at - timedelta(days=3), status='closed', criteria_json=[], roster_json={})
            db.session.add(r)
            db.session.flush()
            for i, (rk, reviewer) in enumerate(who.items()):
                for j, (ek, reviewee) in enumerate(who.items()):
                    if rk == ek:
                        continue
                    at10 = 7 + (i + j + n) % 4
                    qu10 = 6 + (i * 2 + j + n) % 5
                    db.session.add(MatrixReview(round_id=r.id, project_id=p.id, reviewer_id=reviewer.id, reviewee_id=reviewee.id,
                                                attitude10=at10, quality10=qu10, attitude=(at10 + 1) // 2,
                                                quality=(qu10 + 1) // 2, comment=''))
        if n == 1:
            db.session.add(Meeting(project_id=p.id, host_id=who[lead].id, title='Thống nhất phạm vi sprint hỗ trợ',
                                   room_name='showcase-minutes', status='ended', ended_at=at - timedelta(days=2),
                                   notes='Kết luận: ưu tiên sửa lỗi tạo phiếu và kiểm thử luồng tiếp nhận.\n'
                                         'Link cuộc họp: https://meet.google.com/'))
            db.session.add(HelpRequest(project_id=p.id, requested_by=who[lead].id, assigned_to=teacher.id,
                                       subject='Xin hướng dẫn phạm vi kiểm thử',
                                       content='Nhóm cần xác nhận phạm vi kiểm thử cho khách chưa đăng nhập.'))
        db.session.flush()
    # In-app notifications go through the normal outbox so the worker creates them.
    for t in Task.query.join(Project).filter(Project.team_name != '', Task.status.in_(['todo', 'in_progress'])):
        if t.due_at < at and TaskParticipant.query.filter_by(task_id=t.id, user_id=who['MA'].id).first():
            db.session.add(OutboxEvent(event_type='deadline.reminder', aggregate_id=t.project_id, payload={
                'recipients': [who['MA'].id], 'subject': 'Quá hạn: ' + t.title, 'path': f'/tasks/{t.id}'}))
    db.session.add(RuntimeSetting(key=KEY, value={'version': 1}))
    db.session.commit()
    return True
