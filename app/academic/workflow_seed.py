"""Local demo data. Runs once per database; never resets user changes on restart.

The data is varied but reproducible (fixed random seed): real Vietnamese names,
a different product and team name for every group, course-specific tasks,
mixed statuses, deadlines, resubmissions and reviews. Account emails stay as in
README (admin, gv1, sv1…sv36). A few first records are fixed because the test
suite and docs/UAT.md use them: course 1 group 1 = sv1 (leader) … sv6, task 1 is
shared by sv2 and sv3 and was returned once, sv31…sv36 have no group in course 1.
"""
import hashlib
import random
from datetime import timedelta
from werkzeug.security import generate_password_hash
from .core import *
from ..models import Workspace, WorkspaceMember, ProjectMember
from ..models.teamwork import Meeting, MatrixReview
from ..models.workflow import EvidenceCriterion, SubmissionEvidence, SubmissionReferral

SEED = 20261127

HO = ['Nguyễn', 'Trần', 'Lê', 'Phạm', 'Hoàng', 'Vũ', 'Đặng', 'Bùi', 'Đỗ', 'Ngô', 'Dương', 'Lý', 'Phan', 'Võ', 'Trịnh', 'Đinh', 'Mai', 'Tạ']
DEM = ['Văn', 'Thị', 'Minh', 'Ngọc', 'Gia', 'Thanh', 'Quốc', 'Hải', 'Thu', 'Đức', 'Khánh', 'Bảo', 'Phương', 'Tuấn', 'Hoài', 'Diệu']
TEN = ['An', 'Bình', 'Chi', 'Dũng', 'Giang', 'Hà', 'Hiếu', 'Khoa', 'Lan', 'Linh', 'Long', 'Mai', 'Nam', 'Nhung', 'Phong', 'Quân',
       'Sơn', 'Tâm', 'Trang', 'Tú', 'Uyên', 'Vy', 'Yến', 'Hưng', 'Thảo', 'Huy', 'Ngân', 'Đạt', 'Hằng', 'Kiên', 'Oanh', 'Phúc',
       'Quyên', 'Thắng', 'Vân', 'Duy', 'Hạnh', 'Trung']

TEAMS = ['Đội Sao Mai', 'Đội Bình Minh', 'Đội Tia Chớp', 'Đội Hải Đăng', 'Đội Phượng Hoàng', 'Đội Cánh Diều', 'Đội Mặt Trời',
         'Đội Gió Bắc', 'Đội Thủy Tinh', 'Đội Hoa Sen', 'Đội Đại Bàng', 'Đội Ánh Dương', 'Đội Lục Bảo', 'Đội Sông Hồng',
         'Đội Trúc Xanh', 'Đội Kim Cương', 'Đội Thiên Hà', 'Đội Sóng Biển', 'Đội Ngân Hà', 'Đội Cầu Vồng']

# (code, course title, assignment title, products for groups, task pool, evidence criteria)
COURSES = [
    ('CNTT1188', 'Lập trình Web', 'Xây dựng website quản lý thư viện',
     ['Thư viện số Sao Khuê', 'BookHub mượn trả sách', 'Thư viện khoa Kinh tế', 'Góc đọc cộng đồng', 'Kho tài liệu mở'],
     ['Thiết kế giao diện đăng nhập', 'Xây dựng API quản lý sách', 'Thiết kế cơ sở dữ liệu', 'Kiểm thử phân quyền',
      'Tổng hợp mã nguồn', 'Viết báo cáo sản phẩm', 'Trang tìm kiếm sách nâng cao', 'Chức năng gia hạn mượn sách',
      'Thông báo sách quá hạn qua email', 'Giao diện điện thoại cho bạn đọc'],
     ['Ảnh chụp giao diện', 'Mã nguồn chạy được', 'Kịch bản kiểm thử']),
    ('CNTT1117', 'Phân tích và thiết kế hệ thống', 'Phân tích hệ thống quản lý bán hàng',
     ['Chuỗi cà phê Mộc', 'Siêu thị mini 24h', 'Cửa hàng điện máy Hòa Phát', 'Nhà sách Phương Nam', 'Cửa hàng nông sản sạch'],
     ['Khảo sát quy trình bán hàng', 'Vẽ sơ đồ use case', 'Đặc tả use case thanh toán', 'Vẽ sơ đồ lớp', 'Thiết kế sơ đồ tuần tự',
      'Thiết kế giao diện mẫu', 'Tổng hợp tài liệu đặc tả yêu cầu', 'Rà soát mô hình dữ liệu'],
     ['Sơ đồ UML', 'Tài liệu đặc tả']),
    ('CNTT1159', 'Quản lý dự án Công nghệ thông tin', 'Lập kế hoạch dự án phần mềm',
     ['Dự án app giao đồ ăn', 'Dự án cổng tuyển sinh', 'Dự án số hóa hồ sơ', 'Dự án ví điện tử nội bộ', 'Dự án CRM cho trung tâm Anh ngữ'],
     ['Lập bảng phân rã công việc WBS', 'Ước lượng chi phí dự án', 'Lập biểu đồ Gantt', 'Phân tích rủi ro', 'Kế hoạch truyền thông',
      'Biên bản họp khởi động', 'Báo cáo tiến độ giữa kỳ', 'Kế hoạch quản lý chất lượng'],
     ['Kế hoạch dự án', 'Biên bản họp']),
    ('TIKT1130', 'Cơ sở dữ liệu', 'Thiết kế cơ sở dữ liệu cho doanh nghiệp',
     ['CSDL bệnh viện tư', 'CSDL khách sạn biển', 'CSDL trường mầm non', 'CSDL xưởng may', 'CSDL rạp chiếu phim'],
     ['Xác định thực thể và thuộc tính', 'Vẽ sơ đồ ERD', 'Chuẩn hóa dạng 3NF', 'Viết script tạo bảng', 'Nhập dữ liệu mẫu',
      'Viết 20 câu truy vấn báo cáo', 'Tạo view và chỉ mục', 'Viết thủ tục lưu trữ thống kê'],
     ['Sơ đồ ERD', 'Script SQL']),
    ('CNTT1152', 'Hệ quản trị cơ sở dữ liệu', 'Quản trị và tối ưu hệ quản trị CSDL',
     ['Tối ưu CSDL bán vé', 'Sao lưu CSDL ngân hàng mô phỏng', 'Phân quyền CSDL bệnh án', 'Giám sát CSDL thương mại', 'Nhân bản CSDL kho vận'],
     ['Cài đặt và cấu hình máy chủ', 'Thiết lập phân quyền người dùng', 'Lập lịch sao lưu tự động', 'Phục hồi dữ liệu thử nghiệm',
      'Đo hiệu năng truy vấn', 'Tối ưu chỉ mục', 'Viết trigger kiểm tra dữ liệu', 'Báo cáo giám sát hiệu năng'],
     ['Báo cáo hiệu năng', 'Ảnh chụp cấu hình']),
    ('CNTT1180', 'Lập trình Python', 'Ứng dụng Python xử lý dữ liệu',
     ['Phân tích giá nhà Hà Nội', 'Bot nhắc lịch học', 'Thống kê điểm sinh viên', 'Dự báo doanh thu quán ăn', 'Trích xuất hóa đơn PDF'],
     ['Thu thập dữ liệu nguồn', 'Làm sạch dữ liệu với pandas', 'Vẽ biểu đồ thống kê', 'Viết hàm xử lý chính', 'Viết kiểm thử pytest',
      'Đóng gói chương trình', 'Viết README hướng dẫn chạy', 'Trình bày notebook kết quả'],
     ['Notebook kết quả', 'Mã nguồn chạy được']),
    ('CNTT1153', 'Lập trình Java', 'Ứng dụng Java quản lý nghiệp vụ',
     ['Quản lý phòng trọ', 'Quản lý gara ô tô', 'Quản lý phòng gym', 'Quản lý thư viện trường', 'Quản lý tiệm bánh'],
     ['Thiết kế lớp đối tượng', 'Xây dựng màn hình Swing', 'Kết nối JDBC', 'Chức năng thêm sửa xóa', 'Xuất báo cáo Excel',
      'Viết kiểm thử JUnit', 'Xử lý ngoại lệ và nhập liệu', 'Đóng gói file chạy'],
     ['Mã nguồn chạy được', 'Báo cáo kiểm thử']),
    ('CNTT1140', 'Trí tuệ nhân tạo', 'Ứng dụng học máy giải bài toán thực tế',
     ['Phân loại email rác', 'Nhận diện chữ viết tay', 'Gợi ý phim cá nhân', 'Dự đoán rời bỏ khách hàng', 'Phân tích cảm xúc bình luận'],
     ['Khảo sát bài toán và dữ liệu', 'Tiền xử lý dữ liệu', 'Huấn luyện mô hình cơ sở', 'Tinh chỉnh siêu tham số', 'Đánh giá mô hình',
      'Xây dựng giao diện demo', 'Viết báo cáo phương pháp', 'Chuẩn bị slide thuyết trình'],
     ['Báo cáo đánh giá mô hình', 'Mã nguồn chạy được']),
]

NOTES = ['Đã hoàn thành phần chính, kèm tệp kết quả và cách kiểm tra.', 'Bổ sung theo góp ý lần trước, đã chạy lại toàn bộ.',
         'Đã kiểm tra trên máy tính và điện thoại.', 'Gửi bản hoàn chỉnh, có hướng dẫn sử dụng ngắn.', 'Đính kèm ảnh chụp kết quả chạy thử.']
RETURNS = ['Thiếu ảnh chụp màn hình kết quả.', 'Cần bổ sung trường hợp lỗi khi nhập sai dữ liệu.', 'Tài liệu chưa khớp phiên bản mã nguồn.',
           'Chưa ghi rõ cách chạy chương trình.', 'Số liệu ở bảng tổng hợp chưa khớp dữ liệu gốc.']
OUTPUTS = ['Tệp kết quả có thể mở và kiểm tra, kèm mô tả ngắn cách dùng.', 'Mã nguồn hoặc tài liệu đã rà soát, kèm ảnh chụp kết quả.',
           'Bản báo cáo ngắn nêu kết quả, vấn đề còn lại và cách kiểm tra.']


def seed_demo():
    if not db.session.get(RuntimeSetting, 'workspace_demo_v2'):
        seed_base()
    from .showcase_seed import seed_showcase_projects
    seed_showcase_projects()
    seed_schedule_demo()


def unique_names(rnd, n):
    out, seen = [], set()
    while len(out) < n:
        name = f'{rnd.choice(HO)} {rnd.choice(DEM)} {rnd.choice(TEN)}'
        if name not in seen:
            seen.add(name)
            out.append(name)
    return out


def seed_base():
    need(not CourseOffering.query.first(), message='Dùng database mới cho dữ liệu demo mới; không tự ghi đè dữ liệu cũ')
    from ..common.storage import root
    rnd = random.Random(SEED)
    password = generate_password_hash('12345')
    at = now().replace(second=0, microsecond=0)
    naive = lambda d: d.replace(tzinfo=None)

    def user(email, name, role='user'):
        u = User(email=email, full_name=name, role=role, password_hash=password)
        db.session.add(u)
        db.session.flush()
        return u

    admin = user('admin@gmail.com', 'Quản trị hệ thống', 'admin')
    gv = user('gv1@gmail.com', 'Giảng viên Nguyễn Minh', 'instructor')
    students = [user(f'sv{i}@gmail.com', name) for i, name in enumerate(unique_names(rnd, 36), 1)]
    code_of = {u.id: f'1122{4000 + i:04}' for i, u in enumerate(students, 1)}

    def event(action, etype, eid, pid, actor, when, reason=None):
        db.session.add(AuditEvent(action=action, entity_type=etype, entity_id=eid, project_id=pid, actor_id=actor.id,
                                  request_id='seed', reason=reason, created_at=when))

    def store(task, owner, name, text):
        content = text.encode()
        key = hashlib.md5(f'demo-{task.id}-{name}'.encode()).hexdigest()
        (root() / key).parent.mkdir(parents=True, exist_ok=True)
        (root() / key).write_bytes(content)
        a = EvidenceAsset(task_id=task.id, uploaded_by=owner.id, kind='file', storage_key=key, original_filename=name,
                          mime_type='text/plain', sha256=hashlib.sha256(content).hexdigest(), size_bytes=len(content),
                          integrity_status='fixed_file')
        db.session.add(a)
        db.session.flush()
        return a

    def submission(t, p, people, by, n, status, when, due, reviewer=None, reason=None, crit=None):
        asset = store(t, by, f'{slug(t.title)}-lan-{n}.txt', f'# {t.title}\n\nLần nộp {n}: {p.name}.\n')
        rev = EvidenceRevision(task_id=t.id, revision_no=n, description=rnd.choice(NOTES), created_by=by.id, created_at=when)
        db.session.add(rev)
        db.session.flush()
        db.session.add(EvidenceRevisionAsset(revision_id=rev.id, asset_id=asset.id))
        s = TaskSubmission(task_id=t.id, revision_id=rev.id, attempt_no=n, submitted_by=by.id,
                           participant_ids=sorted(u.id for u in people), received_at=when, submitted_due_at=due,
                           status=status, created_at=when, reviewed_by=reviewer.id if reviewer else None,
                           reviewed_at=when + timedelta(hours=rnd.randint(1, 9)) if reviewer else None, review_reason=reason)
        db.session.add(s)
        db.session.flush()
        if crit:
            db.session.add(SubmissionEvidence(submission_id=s.id, criterion_id=crit.id, asset_id=asset.id))
        t.latest_submission_id = s.id
        event('task.submitted', 'task_submission', s.id, p.id, by, when)
        if reviewer:
            event('submission.' + status, 'task_submission', s.id, p.id, reviewer, s.reviewed_at, reason)
        if status == 'accepted':
            t.completed_at = naive(s.reviewed_at)
        return s

    def make_task(p, a, team, leader, title, status, resp, collab, due, crits, fixed_subs=None):
        created = at - timedelta(days=rnd.randint(6, 16), hours=rnd.randint(0, 22))
        people = [resp] + collab
        t = Task(project_id=p.id, title=title, description=rnd.choice(OUTPUTS), status=status,
                 priority=rnd.choices(['low', 'medium', 'high'], weights=[2, 5, 3])[0], points=rnd.choice([1, 1, 2, 2, 3, 5]),
                 created_by=leader.id, assignee_id=resp.id, primary_assignee_id=resp.id, due_at=due, original_due_at=due,
                 created_at=naive(created), updated_at=naive(created))
        db.session.add(t)
        db.session.flush()
        for k, u in enumerate(people):
            db.session.add(TaskParticipant(task_id=t.id, user_id=u.id, role='responsible' if k == 0 else 'collaborator'))
        event('task.created', 'task', t.id, p.id, leader, created)
        if status == 'todo':
            return t
        event('task.started', 'task', t.id, p.id, resp, created + timedelta(hours=rnd.randint(2, 30)))
        reviewers = [u for u in team if u not in people]
        if fixed_subs is not None:
            plan = fixed_subs
        elif status == 'in_progress':
            plan = ['returned'] * rnd.choice([0, 0, 0, 1, 1, 2])
        elif status == 'review':
            plan = ['returned'] * rnd.choice([0, 0, 1]) + ['pending']
        else:
            plan = ['returned'] * rnd.choice([0, 0, 1]) + ['accepted']
        if not reviewers:
            plan = [x for x in plan if x == 'pending']
            if status == 'done':
                t.status = 'review'
                plan = ['pending']
        start = created + timedelta(days=1)
        for n, st in enumerate(plan, 1):
            when = min(start + timedelta(days=n * rnd.uniform(0.8, 2.2)), at - timedelta(hours=(len(plan) - n) * 5 + rnd.randint(1, 4)))
            last = n == len(plan)
            sub_due = due if last else when + timedelta(hours=rnd.choice([-8, 6, 20]))
            reviewer = None if st == 'pending' else (leader if leader in reviewers and rnd.random() < 0.5 else rnd.choice(reviewers))
            reason = rnd.choice(RETURNS) if st == 'returned' else ('Đạt yêu cầu.' if st == 'accepted' else None)
            crit = rnd.choice(crits) if crits and rnd.random() < 0.55 else None
            submission(t, p, people, rnd.choice(people), n, st, when, sub_due, reviewer, reason, crit)
        return t

    groups_by_course = []
    for ci, (code, title, atitle, products, pool, crit_titles) in enumerate(COURSES):
        w = Workspace(name=code, description=title, owner_id=gv.id)
        db.session.add(w)
        db.session.flush()
        c = CourseOffering(code=code + '-04', title=title, term='HK1 · 2026–2027', status='active', workspace_id=w.id, created_by=gv.id)
        db.session.add(c)
        db.session.flush()
        for u in [gv] + students:
            db.session.add(WorkspaceMember(workspace_id=w.id, user_id=u.id, role='owner' if u == gv else 'member'))
            db.session.add(CourseEnrollment(course_id=c.id, user_id=u.id, role='instructor' if u == gv else 'student',
                                            student_code=None if u == gv else code_of[u.id]))
        a = Assignment(course_id=c.id, title=atitle,
                       brief=f'{atitle}. Mỗi nhóm chọn một bối cảnh cụ thể, phân công rõ đầu ra, hạn hoàn thành và bàn giao sản phẩm kèm báo cáo.',
                       status='active', is_hidden=False, due_at=at + timedelta(days=rnd.randint(30, 45)), group_min=3, group_max=8,
                       group_mode='self' if ci % 3 != 2 else 'teacher', formation_due_at=at + timedelta(days=10))
        db.session.add(a)
        db.session.flush()
        crits = []
        for k, ct in enumerate(crit_titles):
            cr = EvidenceCriterion(assignment_id=a.id, title=ct, created_by=gv.id, is_active=not (ci == 2 and k == 1))
            db.session.add(cr)
            db.session.flush()
            crits.append(cr)
        active_crits = [x for x in crits if x.is_active]
        # Course 1 keeps sv1…sv30 in five groups of six and sv31…sv36 free; other courses shuffle people.
        if ci == 0:
            groups = [students[g * 6:g * 6 + 6] for g in range(5)]
        else:
            people = students[:]
            rnd.shuffle(people)
            sizes = [rnd.randint(4, 7) for _ in range(5)]
            groups, pos = [], 0
            for s in sizes:
                groups.append(people[pos:pos + s])
                pos += s
        teams = rnd.sample(TEAMS, 5)
        course_groups = []
        for gi, members in enumerate(groups):
            status = 'active'
            if ci in (2, 5) and gi == 4:
                status = 'pending'
            p = Project(name=products[gi], team_name=teams[gi], description=atitle, workspace_id=w.id, created_by=members[0].id,
                        assignment_id=a.id, mode='academic', status=status, created_at=naive(at - timedelta(days=20)))
            db.session.add(p)
            db.session.flush()
            leader = members[0] if ci == 0 else rnd.choice(members)
            for u in members:
                role = 'leader' if u == leader else 'member'
                db.session.add(AssignmentMembership(assignment_id=a.id, project_id=p.id, user_id=u.id, role=role))
                db.session.add(ProjectMember(project_id=p.id, user_id=u.id, project_role='manager' if role == 'leader' else 'member'))
            event('group.assigned', 'project', p.id, p.id, leader, at - timedelta(days=19, hours=rnd.randint(0, 10)))
            course_groups.append((p, members, leader))
            if status != 'active':
                continue
            if ci == 0 and gi == 0:
                # Fixed records used by tests and docs/UAT.md.
                u = members
                fixed = [
                    ('Thiết kế giao diện đăng nhập', 'in_progress', u[1], [u[2]], at + timedelta(hours=20), ['returned']),
                    ('Xây dựng API quản lý sách', 'todo', u[2], [], at + timedelta(days=3), []),
                    ('Thiết kế cơ sở dữ liệu', 'done', u[3], [], at - timedelta(days=1), ['accepted']),
                    ('Kiểm thử phân quyền', 'review', u[4], [], at + timedelta(days=4), ['pending']),
                ]
                for title_, st, resp, collab, due, plan in fixed:
                    t = make_task(p, a, members, leader, title_, st, resp, collab, due, active_crits, fixed_subs=plan)
                    if title_ == 'Thiết kế giao diện đăng nhập':
                        t.priority = 'high'
                        s = db.session.get(TaskSubmission, t.latest_submission_id)
                        s.review_reason = 'Bổ sung trạng thái báo lỗi khi nhập sai mật khẩu và kiểm tra trên điện thoại.'
                        s.reviewed_by = leader.id
                extra = rnd.sample(pool[4:], 3)
            else:
                extra = rnd.sample(pool, rnd.randint(4, 7))
            for title_ in extra:
                st = rnd.choices(['todo', 'in_progress', 'review', 'done'], weights=[3, 4, 2, 3])[0]
                due = at + timedelta(hours=rnd.randint(-110, 260))
                if st == 'done':
                    due = at - timedelta(hours=rnd.randint(5, 150))
                resp = rnd.choice(members)
                collab = rnd.sample([x for x in members if x != resp], k=rnd.choices([0, 1, 2], weights=[6, 3, 1])[0])
                make_task(p, a, members, leader, title_, st, resp, collab, min(due, a.due_at - timedelta(hours=1)), active_crits)
        groups_by_course.append((c, a, course_groups))

    # Peer rounds already closed in some courses, so averages and scores have data.
    for c, a, course_groups in groups_by_course[1:6]:
        r = PeerRound(assignment_id=a.id, title='Đánh giá giữa kỳ', opens_at=at - timedelta(days=12), closes_at=at - timedelta(days=4),
                      status='closed', criteria_json=[], roster_json={})
        db.session.add(r)
        db.session.flush()
        for p, members, _ in course_groups:
            if p.status != 'active':
                continue
            for rv in members:
                for re_ in members:
                    if rv != re_ and rnd.random() < 0.75:
                        a10, q10 = rnd.randint(5, 10), rnd.randint(5, 10)
                        db.session.add(MatrixReview(round_id=r.id, project_id=p.id, reviewer_id=rv.id, reviewee_id=re_.id,
                                                    attitude10=a10, quality10=q10, attitude=(a10 + 1) // 2, quality=(q10 + 1) // 2, comment=''))
    # A few help requests, minutes, referrals and in-app notifications at varied times.
    helps = ['Xin hướng dẫn phạm vi chức năng bắt buộc', 'Nhóm chưa thống nhất cách chia khối lượng', 'Cần góp ý cấu trúc báo cáo',
             'Lỗi khi chạy trên máy phòng thực hành']
    for c, a, course_groups in groups_by_course:
        for p, members, leader in course_groups:
            if p.status != 'active':
                continue
            if rnd.random() < 0.25:
                db.session.add(HelpRequest(project_id=p.id, requested_by=rnd.choice(members).id, assigned_to=gv.id,
                                           subject=rnd.choice(helps), content='Nhóm mô tả khó khăn và mong giảng viên góp ý hướng xử lý.',
                                           created_at=at - timedelta(hours=rnd.randint(2, 60))))
            if rnd.random() < 0.4 or (p.id == course_groups[0][0].id and c.id == groups_by_course[0][0].id):
                db.session.add(Meeting(project_id=p.id, host_id=leader.id, title=rnd.choice(['Thống nhất đầu ra tuần 1', 'Họp chốt phân công',
                                                                                                  'Rà soát tiến độ giữa kỳ']),
                                       room_name=f'seed-minutes-{p.id}', status='ended', ended_at=at - timedelta(days=rnd.randint(1, 6)),
                                       notes=f'Thành viên tham dự: {len(members)} thành viên.\nKết luận: ưu tiên các đầu việc sắp đến hạn; '
                                             'mỗi công việc có tệp bàn giao và hướng dẫn kiểm tra.\nLink cuộc họp: https://meet.google.com/'))
            pending = [t for t in Task.query.filter_by(project_id=p.id, status='review')]
            if pending and rnd.random() < 0.2 and p.id != course_groups[0][0].id:
                t = pending[0]
                s = db.session.get(TaskSubmission, t.latest_submission_id)
                reason = 'Nhóm chưa thống nhất đánh giá, nhờ giảng viên xem giúp lần nộp này.'
                db.session.add(SubmissionReferral(submission_id=s.id, project_id=p.id, referred_by=leader.id, instructor_id=gv.id, reason=reason))
                event('submission.referred', 'task_submission', s.id, p.id, leader, at - timedelta(hours=rnd.randint(1, 20)), reason)
                notification(gv, 'submission.referred', 'Bài được chuyển cho bạn duyệt', f'{t.title} · {p.name} · Lần {s.attempt_no}',
                             f'/tasks/{t.id}?submission={s.id}#submission-{s.id}', at - timedelta(hours=rnd.randint(1, 20)))
            for t in Task.query.filter_by(project_id=p.id).filter(Task.status.in_(['todo', 'in_progress'])):
                if t.due_at < at + timedelta(hours=24):
                    late = t.due_at < at
                    for x in TaskParticipant.query.filter_by(task_id=t.id):
                        notification(db.session.get(User, x.user_id), 'deadline.reminder', 'Nhắc hạn công việc',
                                     ('Quá hạn: ' if late else 'Sắp đến hạn: ') + t.title, f'/tasks/{t.id}',
                                     at - timedelta(minutes=rnd.randint(5, 600)))
    db.session.add(RuntimeSetting(key='workspace_demo_v2', value={'version': 3}))
    db.session.add(RuntimeSetting(key='demo_clock', value={}))
    db.session.commit()


def notification(u, kind, title, body, path, when):
    """In-app notification with a realistic past time (outbox already processed)."""
    e = OutboxEvent(event_type=kind, aggregate_id=0, payload={'recipients': [u.id], 'subject': body, 'path': path},
                    processed_at=when, created_at=when)
    db.session.add(e)
    db.session.flush()
    db.session.add(Notification(recipient_id=u.id, event_id=e.id, title=title, body=body, target_path=path, created_at=when))


def slug(text):
    import unicodedata
    s = unicodedata.normalize('NFKD', text.replace('đ', 'd').replace('Đ', 'D')).encode('ascii', 'ignore').decode().lower()
    return '-'.join(''.join(ch if ch.isalnum() else ' ' for ch in s).split())[:40] or 'san-pham'


def seed_schedule_demo():
    """Timeline entries for demo accounts (runs once; also fills older demo databases)."""
    from ..models.workflow import ScheduleItem
    if db.session.get(RuntimeSetting, 'schedule_demo_v1'):
        return
    rnd = random.Random(SEED + 7)
    today = now().date()
    plans = [  # (category, title, start offset, length in days, shared with a project?)
        ('meeting', 'Họp nhóm chốt phân công tuần', 0, 1, True),
        ('study', 'Ôn lại kiến thức nền cho phần việc được giao', -1, 2, False),
        ('deadline', 'Mốc nộp bản nháp báo cáo', 3, 1, True),
        ('review', 'Rà soát chéo bài nộp của nhóm', 4, 2, True),
        ('personal', 'Lịch thi giữa kỳ môn khác', 6, 1, False),
        ('study', 'Đọc tài liệu tham khảo và ghi chú', 2, 4, False),
        ('meeting', 'Họp với giảng viên hướng dẫn', 8, 1, True),
        ('deadline', 'Chốt bản bàn giao sản phẩm', 10, 1, True),
        ('other', 'Chuẩn bị slide thuyết trình', 7, 3, False),
    ]
    emails = ['sv1@gmail.com', 'sv2@gmail.com', 'sv3@gmail.com', 'minhanh@gmail.com', 'thuha@gmail.com', 'quocbao@gmail.com']
    for email in emails:
        u = User.query.filter_by(email=email).first()
        if not u:
            continue
        pids = [m.project_id for m in AssignmentMembership.query.filter_by(user_id=u.id, status='active').order_by(AssignmentMembership.id)]
        for cat, title, off, length, shared in rnd.sample(plans, 6):
            start = today + timedelta(days=off + rnd.choice([0, 0, 1]))
            pid = pids[rnd.randrange(len(pids))] if shared and pids else None
            db.session.add(ScheduleItem(owner_id=u.id, project_id=pid, title=title, category=cat, start_date=start,
                                        end_date=start + timedelta(days=length - 1),
                                        note='Mục lịch mẫu, có thể kéo thả sang ngày khác hoặc sửa nội dung.'))
    db.session.add(RuntimeSetting(key='schedule_demo_v1', value={'version': 1}))
    db.session.commit()
