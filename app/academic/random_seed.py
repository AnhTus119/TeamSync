"""Random demo data for trying the UI: courses, projects, tasks, submissions, reviews.

Each call adds one new batch (course codes RND-<batch>-<n>) and never deletes data.
Every record keeps the business rules: task status matches its submissions, reviewers
are never in the submission roster, referrals only target pending latest submissions.
"""
import hashlib
import random
from datetime import timedelta
from werkzeug.security import generate_password_hash
from .core import *
from ..models import Workspace, WorkspaceMember, ProjectMember
from ..models.teamwork import MatrixReview, Meeting
from ..models.workflow import EvidenceCriterion, SubmissionEvidence, SubmissionReferral

HO = ['Nguyễn', 'Trần', 'Lê', 'Phạm', 'Hoàng', 'Vũ', 'Đặng', 'Bùi', 'Đỗ', 'Ngô', 'Dương', 'Lý']
DEM = ['Văn', 'Thị', 'Minh', 'Ngọc', 'Gia', 'Thanh', 'Quốc', 'Hải', 'Thu', 'Đức', 'Khánh', 'Bảo']
TEN = ['An', 'Bình', 'Chi', 'Dũng', 'Giang', 'Hà', 'Hiếu', 'Khoa', 'Lan', 'Linh', 'Long', 'Mai', 'Nam', 'Nhung',
       'Phong', 'Quân', 'Sơn', 'Tâm', 'Trang', 'Tú', 'Uyên', 'Vy', 'Yến', 'Hưng']
SUBJECTS = ['Lập trình di động', 'Phát triển phần mềm Agile', 'Kiểm thử phần mềm', 'Thương mại điện tử',
            'Hệ thống thông tin quản lý', 'Khai phá dữ liệu', 'An toàn thông tin', 'Điện toán đám mây',
            'Thiết kế trải nghiệm người dùng', 'Phân tích dữ liệu lớn với nhiều nguồn dữ liệu không đồng nhất']
PRODUCTS = ['Ứng dụng đặt lịch khám', 'Cổng tuyển sinh', 'Hệ thống quản lý kho', 'Ứng dụng học từ vựng',
            'Sàn giao dịch đồ cũ', 'Bảng điều khiển IoT', 'Ứng dụng chia sẻ xe', 'Trợ lý ghi chú họp',
            'Hệ thống quản lý thư viện số kèm đề xuất sách cá nhân hóa theo lịch sử mượn']
TEAMS = ['Đội Sao Mai', 'Đội Bình Minh', 'Đội Tia Chớp', 'Đội Hải Đăng', 'Đội Phượng Hoàng', 'Đội Cánh Diều',
         'Đội Kỹ thuật và Kiểm thử chất lượng phần mềm']
VERBS = ['Thiết kế', 'Xây dựng', 'Kiểm thử', 'Viết tài liệu', 'Rà soát', 'Tối ưu', 'Tích hợp', 'Chuẩn hóa', 'Triển khai']
OBJECTS = ['màn hình đăng nhập', 'API thanh toán', 'cơ sở dữ liệu người dùng', 'luồng đặt hàng', 'báo cáo tuần',
           'giao diện điện thoại', 'phân quyền quản trị', 'bộ dữ liệu mẫu', 'kịch bản kiểm thử hồi quy',
           'tài liệu hướng dẫn sử dụng cho người dùng cuối và quản trị viên hệ thống']
CRITERIA = ['Kiểm thử chức năng', 'Tài liệu thiết kế', 'Mã nguồn chạy được', 'Báo cáo hiệu năng', 'Biên bản nghiệm thu']
NOTES = ['Đã hoàn thành phần chính, đính kèm tệp kết quả.', 'Bổ sung theo góp ý lần trước.',
         'Đã kiểm thử trên máy tính và điện thoại.', 'Gửi bản nháp để nhóm góp ý sớm.']
RETURNS = ['Thiếu ảnh chụp màn hình kết quả.', 'Cần bổ sung trường hợp lỗi.', 'Tài liệu chưa khớp phiên bản mã nguồn.',
           'Chưa xử lý trường hợp người dùng chưa đăng nhập.']


def seed_random(projects=6, tasks=8, seed=None, students=12):
    rnd = random.Random(seed)
    batches = db.session.get(RuntimeSetting, 'random_batches')
    batch = (batches.value.get('count', 0) if batches else 0) + 1
    if batches:
        batches.value = {'count': batch}
    else:
        db.session.add(RuntimeSetting(key='random_batches', value={'count': batch}))
    from ..common.storage import root
    pw = generate_password_hash('12345')
    at = now().replace(second=0, microsecond=0)
    naive = lambda d: d.replace(tzinfo=None)

    teacher = User.query.filter_by(email='gv2@gmail.com').first() or User.query.filter_by(role='instructor').first()
    known = [u for u in (User.query.filter_by(email=e).first() for e in
                         ('minhanh@gmail.com', 'thuha@gmail.com', 'quocbao@gmail.com', 'gialinh@gmail.com')) if u]
    pool = []
    for i in range(students):
        email = f'rnd{batch}-{i + 1:02}@gmail.com'
        u = User.query.filter_by(email=email).first()
        if not u:
            u = User(email=email, full_name=f'{rnd.choice(HO)} {rnd.choice(DEM)} {rnd.choice(TEN)}', role='user', password_hash=pw)
            db.session.add(u)
            db.session.flush()
        pool.append(u)

    def audit_at(action, etype, eid, pid, actor, when, reason=None):
        db.session.add(AuditEvent(action=action, entity_type=etype, entity_id=eid, project_id=pid, actor_id=actor.id,
                                  request_id=f'random-{batch}', reason=reason, created_at=when))

    made = {'courses': 0, 'projects': 0, 'tasks': 0, 'submissions': 0}
    for n in range(projects):
        code = f'RND-{batch}-{n + 1:02}'
        w = Workspace(name=code, description='Dữ liệu ngẫu nhiên', owner_id=teacher.id)
        db.session.add(w)
        db.session.flush()
        title = rnd.choice(SUBJECTS)
        c = CourseOffering(code=code, title=title, term=f'Ngẫu nhiên đợt {batch}', status='active', workspace_id=w.id, created_by=teacher.id)
        db.session.add(c)
        db.session.flush()
        size = rnd.randint(3, 6)
        # Demo students take part in most projects so they see the data on login.
        team = rnd.sample(known, k=min(len(known), rnd.randint(1, 3))) + rnd.sample(pool, k=size)
        team = list(dict.fromkeys(team))
        extra = [u for u in rnd.sample(pool, k=3) if u not in team]  # enrolled, no group
        for u in [teacher] + team + extra:
            db.session.add(WorkspaceMember(workspace_id=w.id, user_id=u.id, role='owner' if u == teacher else 'member'))
            db.session.add(CourseEnrollment(course_id=c.id, user_id=u.id, role='instructor' if u == teacher else 'student',
                                            student_code=None if u == teacher else f'R{batch}{u.id:04}'))
        product = rnd.choice(PRODUCTS)
        a = Assignment(course_id=c.id, title=product, brief=f'Xây dựng {product.lower()} và bàn giao sản phẩm chạy được.',
                       status='active', is_hidden=False, due_at=at + timedelta(days=rnd.randint(15, 45)),
                       group_min=3, group_max=8, group_mode=rnd.choice(['self', 'teacher']), formation_due_at=at + timedelta(days=5))
        db.session.add(a)
        db.session.flush()
        crits = []
        for t in rnd.sample(CRITERIA, k=rnd.randint(0, 3)):
            cr = EvidenceCriterion(assignment_id=a.id, title=t, created_by=teacher.id, is_active=rnd.random() > 0.2)
            db.session.add(cr)
            db.session.flush()
            crits.append(cr)
        status = rnd.choices(['active', 'pending', 'draft'], weights=[8, 1, 1])[0]
        p = Project(name=product, team_name=rnd.choice(TEAMS), description=product, workspace_id=w.id,
                    created_by=team[0].id, assignment_id=a.id, mode='academic', status=status)
        db.session.add(p)
        db.session.flush()
        leader = rnd.choice(team)
        for u in team:
            role = 'leader' if u == leader else 'member'
            db.session.add(AssignmentMembership(assignment_id=a.id, project_id=p.id, user_id=u.id, role=role))
            db.session.add(ProjectMember(project_id=p.id, user_id=u.id, project_role='manager' if role == 'leader' else 'member'))
        audit_at('group.assigned', 'project', p.id, p.id, leader, at - timedelta(days=20))
        made['courses'] += 1
        made['projects'] += 1
        if status != 'active':
            continue
        for ti in range(tasks):
            st = rnd.choices(['todo', 'in_progress', 'review', 'done'], weights=[3, 4, 2, 3])[0]
            due = at + timedelta(hours=rnd.randint(-120, 240))
            if due > a.due_at:
                due = a.due_at - timedelta(hours=1)
            created = at - timedelta(days=rnd.randint(8, 18), hours=rnd.randint(0, 20))
            resp = rnd.choice(team)
            collab = rnd.sample([u for u in team if u != resp], k=rnd.choice([0, 0, 1, 2]))
            people = [resp] + collab
            t = Task(project_id=p.id, title=f'{rnd.choice(VERBS)} {rnd.choice(OBJECTS)}', status=st,
                     description='Đầu ra: tệp hoặc liên kết có thể mở và kiểm tra, kèm mô tả cách dùng.',
                     priority=rnd.choice(['low', 'medium', 'high']), points=rnd.choice([1, 1, 2, 3, 5]),
                     created_by=leader.id, assignee_id=resp.id, primary_assignee_id=resp.id, due_at=due,
                     original_due_at=due, created_at=naive(created), updated_at=naive(created))
            db.session.add(t)
            db.session.flush()
            for k, u in enumerate(people):
                db.session.add(TaskParticipant(task_id=t.id, user_id=u.id, role='responsible' if k == 0 else 'collaborator'))
            audit_at('task.created', 'task', t.id, p.id, leader, created)
            made['tasks'] += 1
            if st == 'todo':
                continue
            audit_at('task.started', 'task', t.id, p.id, resp, created + timedelta(hours=3))
            reviewers = [u for u in team if u not in people]
            if st == 'in_progress':
                plan = ['returned'] * (rnd.choice([0, 0, 1, 2]) if reviewers else 0)
            elif st == 'review':
                plan = ['returned'] * (rnd.choice([0, 1, 2]) if reviewers else 0) + ['pending']
            else:
                plan = ['returned'] * rnd.choice([0, 0, 1]) + ['accepted']
                if not reviewers:  # nobody independent: keep it in progress instead of breaking the rule
                    t.status, plan = 'in_progress', []
            for si, sst in enumerate(plan, 1):
                when = created + timedelta(days=si * 2, hours=rnd.randint(1, 10))
                if when > at:
                    when = at - timedelta(hours=len(plan) - si + 1)
                by = rnd.choice(people)
                content = f'# {t.title}\n\nLần nộp {si} — đợt ngẫu nhiên {batch}.\n'.encode()
                key = hashlib.md5(f'random-{batch}-{t.id}-{si}'.encode()).hexdigest()
                (root() / key).parent.mkdir(parents=True, exist_ok=True)
                (root() / key).write_bytes(content)
                asset = EvidenceAsset(task_id=t.id, uploaded_by=by.id, kind='file', storage_key=key, original_filename=f'ket-qua-lan-{si}.txt',
                                      mime_type='text/plain', sha256=hashlib.sha256(content).hexdigest(), size_bytes=len(content),
                                      integrity_status='fixed_file')
                db.session.add(asset)
                db.session.flush()
                rev = EvidenceRevision(task_id=t.id, revision_no=si, description=rnd.choice(NOTES), created_by=by.id, created_at=when)
                db.session.add(rev)
                db.session.flush()
                db.session.add(EvidenceRevisionAsset(revision_id=rev.id, asset_id=asset.id))
                reviewer = rnd.choice(reviewers) if sst != 'pending' and reviewers else None
                s = TaskSubmission(task_id=t.id, revision_id=rev.id, attempt_no=si, submitted_by=by.id,
                                   participant_ids=sorted(u.id for u in people), received_at=when,
                                   submitted_due_at=due if si == len(plan) else when + timedelta(hours=rnd.choice([-6, 12])),
                                   status=sst, created_at=when, reviewed_by=reviewer.id if reviewer else None,
                                   reviewed_at=when + timedelta(hours=2) if reviewer else None,
                                   review_reason=(rnd.choice(RETURNS) if sst == 'returned' else 'Đạt yêu cầu.') if reviewer else None)
                db.session.add(s)
                db.session.flush()
                active = [cr for cr in crits if cr.is_active]
                if active and rnd.random() < 0.6:
                    db.session.add(SubmissionEvidence(submission_id=s.id, criterion_id=rnd.choice(active).id, asset_id=asset.id))
                t.latest_submission_id = s.id
                audit_at('task.submitted', 'task_submission', s.id, p.id, by, when)
                if reviewer:
                    audit_at('submission.' + sst, 'task_submission', s.id, p.id, reviewer, when + timedelta(hours=2), s.review_reason)
                if sst == 'accepted':
                    t.completed_at = naive(when + timedelta(hours=2))
                if sst == 'pending' and rnd.random() < 0.3:
                    reason = 'Nhờ giảng viên xem giúp phần này.'
                    db.session.add(SubmissionReferral(submission_id=s.id, project_id=p.id, referred_by=leader.id,
                                                      instructor_id=teacher.id, reason=reason))
                    audit_at('submission.referred', 'task_submission', s.id, p.id, leader, when + timedelta(hours=1), reason)
                made['submissions'] += 1
        if rnd.random() < 0.6:
            r = PeerRound(assignment_id=a.id, title='Đánh giá ngẫu nhiên', opens_at=at - timedelta(days=9),
                          closes_at=at - timedelta(days=2), status='closed', criteria_json=[], roster_json={})
            db.session.add(r)
            db.session.flush()
            for rv in team:
                for re_ in team:
                    if rv != re_ and rnd.random() < 0.8:
                        a10, q10 = rnd.randint(4, 10), rnd.randint(4, 10)
                        db.session.add(MatrixReview(round_id=r.id, project_id=p.id, reviewer_id=rv.id, reviewee_id=re_.id,
                                                    attitude10=a10, quality10=q10, attitude=(a10 + 1) // 2, quality=(q10 + 1) // 2, comment=''))
        if rnd.random() < 0.4:
            db.session.add(HelpRequest(project_id=p.id, requested_by=leader.id, assigned_to=teacher.id,
                                       subject='Cần hướng dẫn phạm vi sản phẩm', content='Nhóm cần xác nhận phạm vi chức năng bắt buộc.'))
        if rnd.random() < 0.5:
            db.session.add(Meeting(project_id=p.id, host_id=leader.id, title='Họp chốt phân công', room_name=f'random-{batch}-{p.id}',
                                   status='ended', ended_at=at - timedelta(days=1),
                                   notes='Kết luận: chia việc theo module, rà soát lại vào cuối tuần.\nLink cuộc họp: https://meet.google.com/'))
        for u in team:
            db.session.add(OutboxEvent(event_type='group.approved', aggregate_id=p.id, payload={
                'recipients': [u.id], 'subject': f'Bạn được xếp vào {p.name} · {p.team_name}', 'path': f'/projects/{p.id}'}))
    db.session.commit()
    return {'batch': batch, **made, 'students': [u.email for u in pool]}
