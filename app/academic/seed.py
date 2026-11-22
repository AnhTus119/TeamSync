from datetime import timedelta
import hashlib, uuid
from ..extensions import db
from ..common.clock import utcnow
from ..common.storage import root
from ..models import (
    User,
    Workspace,
    WorkspaceMember,
    Project,
    ProjectMember,
    Task,
    Milestone,
)
from ..models.academic import *

PASSWORD = "12345"


def seed_demo():
    if db.session.get(RuntimeSetting, "demo_fixture"):
        update_demo_logins()
        ensure_dashboard_demo_tasks()
        ensure_second_course_demo_tasks()
        return
    t0 = utcnow().replace(second=0, microsecond=0)
    users = {}
    names = {
        "ops": "Vận hành kỹ thuật",
        "coordinator": "Quản lý học phần",
        "gv1": "Giảng viên 1",
        "gv2": "Giảng viên 2",
        "sv1": "Sinh viên 1",
        "sv2": "Sinh viên 2",
        "sv3": "Sinh viên 3",
        "sv4": "Sinh viên 4",
    }
    for key, name in names.items():
        email = key + "@gmail.com"
        if User.query.filter_by(email=email).first():
            raise ValueError(
                "Demo namespace đã có tài khoản. Dùng database demo riêng để tránh ghi đè"
            )
        u = User(
            email=email,
            full_name=name,
            role=(
                "admin"
                if key == "ops"
                else "coordinator" if key == "coordinator" else "user"
            ),
        )
        u.set_password(PASSWORD)
        db.session.add(u)
        db.session.flush()
        users[key] = u
    courses = []
    for n in (1, 2):
        teacher = users[f"gv{n}"]
        w = Workspace(name=f"WEB0{n}", description="Dữ liệu demo", owner_id=teacher.id)
        db.session.add(w)
        db.session.flush()
        c = CourseOffering(
            code=f"WEB0{n}",
            title=(
                "Phân tích dữ liệu trong học tập" if n == 1 else "Phát triển ứng dụng"
            ),
            term="2026–2027 / HK1",
            workspace_id=w.id,
            created_by=users["coordinator"].id,
            status="active",
        )
        db.session.add(c)
        db.session.flush()
        courses.append(c)
        for key, role in [("coordinator", "coordinator"), (f"gv{n}", "instructor")] + (
            [(f"sv{i}", "student") for i in range(1, 5)] if n == 1 else []
        ):
            u = users[key]
            db.session.add(
                CourseEnrollment(
                    course_id=c.id,
                    user_id=u.id,
                    role=role,
                    student_code=f"DEMO{key[-1]}" if role == "student" else None,
                )
            )
            db.session.add(
                WorkspaceMember(
                    workspace_id=w.id,
                    user_id=u.id,
                    role="owner" if role == "instructor" else "member",
                )
            )
    a = Assignment(
        course_id=courses[0].id,
        title="Phân tích khảo sát trải nghiệm học tập",
        brief="Dữ liệu demo: làm sạch dữ liệu, phân tích và báo cáo kết quả khảo sát. Ghi rõ đóng góp cá nhân và dẫn minh chứng theo tiêu chí.",
        status="active",
        opens_at=t0,
        due_at=t0 + timedelta(days=30),
        group_min=1,
        group_max=5,
    )
    db.session.add(a)
    db.session.flush()
    p = AssessmentPolicy(
        assignment_id=a.id,
        revision=1,
        status="published",
        published_at=t0,
        appeal_window_hours=72,
    )
    db.session.add(p)
    db.session.flush()
    a.published_policy_id = p.id
    criteria = []
    from .rubric import DEMO_CRITERIA

    for item in DEMO_CRITERIA:
        c = Criterion(
            policy_id=p.id,
            code=item["code"],
            title=item["title"],
            weight=item["weight"],
            max_score=10,
            description=item["description"],
            evidence_requirement=item["evidence_requirement"],
        )
        db.session.add(c)
        db.session.flush()
        criteria.append(c)
        for j, level in enumerate(item["levels"]):
            db.session.add(CriterionLevel(criterion_id=c.id, ordinal=j, **level))
    groups = []
    for name, keys in [("G01", ["sv1", "sv2", "sv3"]), ("G02", ["sv4"])]:
        pr = Project(
            workspace_id=courses[0].workspace_id,
            name=name,
            description="Dữ liệu demo",
            created_by=users["gv1"].id,
            assignment_id=a.id,
            mode="academic",
            status="active",
        )
        db.session.add(pr)
        db.session.flush()
        groups.append(pr)
        db.session.add(
            GroupInvitation(
                project_id=pr.id,
                user_id=users["gv1"].id,
                invited_by=users[keys[0]].id,
                kind="mentor",
                status="accepted",
                responded_at=t0,
            )
        )
        for i, key in enumerate(keys):
            db.session.add(
                AssignmentMembership(
                    assignment_id=a.id,
                    project_id=pr.id,
                    user_id=users[key].id,
                    role="leader" if i == 0 else "member",
                )
            )
            db.session.add(
                ProjectMember(
                    project_id=pr.id,
                    user_id=users[key].id,
                    project_role="manager" if i == 0 else "member",
                )
            )
    g = groups[0]
    ms = []
    for title, hours in [("Dữ liệu và phân tích", 14 * 24), ("Báo cáo cuối", 28 * 24)]:
        m = Milestone(
            project_id=g.id,
            title=title,
            due_at=t0 + timedelta(hours=hours),
            required=True,
        )
        db.session.add(m)
        db.session.flush()
        ms.append(m)
    tasks = []
    for title, key, hours, cs, mid, collab in [
        ("Làm sạch dữ liệu", "sv2", 24, [0, 2], ms[0].id, "sv1"),
        ("Phân tích", "sv3", 48, [0, 1], ms[0].id, None),
        ("Tổng hợp báo cáo", "sv1", 72, [0, 3], ms[1].id, None),
        ("Kiểm tra bảng hỏi", "sv3", 12, [1], None, None),
    ]:
        t = Task(
            project_id=g.id,
            title=title,
            description="Dữ liệu demo",
            created_by=users["sv1"].id,
            assignee_id=users[key].id,
            primary_assignee_id=users[key].id,
            due_at=t0 + timedelta(hours=hours),
            original_due_at=t0 + timedelta(hours=hours),
            milestone_id=mid,
            points=2,
            created_at=t0.replace(tzinfo=None),
        )
        db.session.add(t)
        db.session.flush()
        tasks.append(t)
        db.session.add(
            TaskParticipant(task_id=t.id, user_id=users[key].id, role="responsible")
        )
        if collab:
            db.session.add(
                TaskParticipant(
                    task_id=t.id, user_id=users[collab].id, role="collaborator"
                )
            )
        for ci in cs:
            db.session.add(TaskCriterion(task_id=t.id, criterion_id=criteria[ci].id))

    # Keep WEB01 compact: the four baseline tasks above are sufficient for demo/UAT.
    demo_tasks = []
    for title, key, day_offset, status, priority, points in demo_tasks:
        due = t0 + timedelta(days=day_offset)
        extra = Task(
            project_id=g.id,
            title=title,
            description="Công việc mẫu phục vụ kiểm thử quy trình phối hợp, deadline và cảnh báo của TeamSync.",
            status=status,
            priority=priority,
            points=points,
            created_by=users["sv1"].id,
            assignee_id=users[key].id,
            primary_assignee_id=users[key].id,
            due_at=due,
            original_due_at=due,
            created_at=(t0 - timedelta(days=5)).replace(tzinfo=None),
        )
        db.session.add(extra)
        db.session.flush()
        db.session.add(TaskParticipant(task_id=extra.id, user_id=users[key].id, role="responsible"))
        if key != "sv1":
            db.session.add(TaskParticipant(task_id=extra.id, user_id=users["sv1"].id, role="collaborator"))

    # G02 is already submitted for assessment so G01 UAT can continue independently.
    g2 = groups[1]
    g2.status = "active"
    m = Milestone(
        project_id=g2.id,
        title="Báo cáo demo G02",
        status="accepted",
        required=True,
        reviewed_by=users["gv1"].id,
        reviewed_at=t0.replace(tzinfo=None),
    )
    db.session.add(m)
    db.session.flush()
    t = Task(
        project_id=g2.id,
        milestone_id=m.id,
        title="Báo cáo G02",
        status="done",
        created_by=users["sv4"].id,
        assignee_id=users["sv4"].id,
        primary_assignee_id=users["sv4"].id,
        due_at=t0 + timedelta(hours=72),
        original_due_at=t0 + timedelta(hours=72),
    )
    db.session.add(t)
    db.session.flush()
    db.session.add(
        TaskParticipant(task_id=t.id, user_id=users["sv4"].id, role="responsible")
    )
    for c in criteria:
        db.session.add(TaskCriterion(task_id=t.id, criterion_id=c.id))
    raw = b"Du lieu demo - bao cao G02"
    key = uuid.uuid4().hex
    (root() / key).write_bytes(raw)
    asset = EvidenceAsset(
        task_id=t.id,
        uploaded_by=users["sv4"].id,
        kind="file",
        storage_key=key,
        original_filename="bao-cao-demo.txt",
        mime_type="text/plain",
        size_bytes=len(raw),
        sha256=hashlib.sha256(raw).hexdigest(),
        integrity_status="fixed_file",
        created_at=t0,
    )
    db.session.add(asset)
    db.session.flush()
    r = EvidenceRevision(
        task_id=t.id,
        revision_no=1,
        description="Dữ liệu demo",
        created_by=users["sv4"].id,
        created_at=t0,
    )
    db.session.add(r)
    db.session.flush()
    db.session.add(EvidenceRevisionAsset(revision_id=r.id, asset_id=asset.id))
    s = TaskSubmission(
        task_id=t.id,
        revision_id=r.id,
        attempt_no=1,
        submitted_by=users["sv4"].id,
        participant_ids=[users["sv4"].id],
        received_at=t0,
        submitted_due_at=t.due_at,
        status="accepted",
        reviewed_by=users["gv1"].id,
        reviewed_at=t0,
    )
    db.session.add(s)
    db.session.flush()
    t.latest_submission_id = s.id
    db.session.add(
        RuntimeSetting(
            key="demo_fixture", value={"t0": t0.isoformat(), "assignment_id": a.id}
        )
    )
    db.session.add(RuntimeSetting(key="demo_clock", value={}))
    db.session.commit()
    ensure_second_course_demo_tasks()


def ensure_second_course_demo_tasks():
    """Create realistic, idempotent work samples in the other demo courses."""
    now_at = utcnow().replace(second=0, microsecond=0)
    coordinator = User.query.filter_by(email="coordinator@gmail.com").first()
    if coordinator is None:
        return
    course_specs = [
        ("WEB02", "Phát triển ứng dụng", "gv2", ("sv1", "sv2", "sv3"),
         "Xây dựng ứng dụng quản lý học tập",
         (("Thiết kế luồng người dùng", "sv1", 4, "in_progress", "high"),
          ("Xây dựng màn hình quản lý công việc", "sv2", 9, "todo", "medium"))),
        ("WEB03", "Cơ sở dữ liệu ứng dụng", "gv1", ("sv2", "sv3", "sv4"),
         "Thiết kế cơ sở dữ liệu bán hàng",
         (("Mô hình hóa dữ liệu và quan hệ", "sv2", 5, "in_progress", "high"),
          ("Viết truy vấn và kiểm thử dữ liệu", "sv4", 11, "todo", "medium"))),
    ]
    for code, title, teacher_key, student_keys, assignment_title, task_specs in course_specs:
        course = CourseOffering.query.filter_by(code=code, term="2026–2027 / HK1").first()
        teacher = User.query.filter_by(email=teacher_key + "@gmail.com").first()
        students = {key: User.query.filter_by(email=key + "@gmail.com").first() for key in student_keys}
        if teacher is None or any(value is None for value in students.values()):
            continue
        if course is None:
            workspace = Workspace(name=code, description="Dữ liệu demo", owner_id=teacher.id)
            db.session.add(workspace)
            db.session.flush()
            course = CourseOffering(code=code, title=title, term="2026–2027 / HK1", workspace_id=workspace.id, created_by=coordinator.id, status="active")
            db.session.add(course)
            db.session.flush()
        for key, user in students.items():
            if not CourseEnrollment.query.filter_by(course_id=course.id, user_id=user.id).first():
                db.session.add(CourseEnrollment(course_id=course.id, user_id=user.id, role="student", status="active", student_code="DEMO" + key[-1]))
            if not WorkspaceMember.query.filter_by(workspace_id=course.workspace_id, user_id=user.id).first():
                db.session.add(WorkspaceMember(workspace_id=course.workspace_id, user_id=user.id, role="member"))
        if not CourseEnrollment.query.filter_by(course_id=course.id, user_id=teacher.id).first():
            db.session.add(CourseEnrollment(course_id=course.id, user_id=teacher.id, role="instructor", status="active"))
        if not WorkspaceMember.query.filter_by(workspace_id=course.workspace_id, user_id=teacher.id).first():
            db.session.add(WorkspaceMember(workspace_id=course.workspace_id, user_id=teacher.id, role="owner"))
        assignment = Assignment.query.filter_by(course_id=course.id, title=assignment_title).first()
        if assignment and Project.query.filter_by(assignment_id=assignment.id).first():
            continue
        if assignment is None:
            assignment = Assignment(course_id=course.id, title=assignment_title, brief=f"Bài tập nhóm thực hành cho học phần {code}.", status="active", opens_at=now_at - timedelta(days=3), due_at=now_at + timedelta(days=21), group_min=1, group_max=5)
            db.session.add(assignment)
            db.session.flush()
        project = Project(workspace_id=course.workspace_id, name="G01", description=f"Nhóm demo lớp {code}", created_by=teacher.id, assignment_id=assignment.id, mode="academic", status="active")
        db.session.add(project)
        db.session.flush()
        for i, (key, user) in enumerate(students.items()):
            db.session.add(AssignmentMembership(assignment_id=assignment.id, project_id=project.id, user_id=user.id, role="leader" if i == 0 else "member", status="active"))
            db.session.add(ProjectMember(project_id=project.id, user_id=user.id, project_role="manager" if i == 0 else "member"))
        for task_title, key, days, status, priority in task_specs:
            user = students[key]
            task = Task(project_id=project.id, title=task_title, description=f"Công việc demo lớp {code}.", status=status, priority=priority, points=2, created_by=teacher.id, assignee_id=user.id, primary_assignee_id=user.id, due_at=now_at + timedelta(days=days), original_due_at=now_at + timedelta(days=days), created_at=(now_at - timedelta(days=2)).replace(tzinfo=None))
            db.session.add(task)
            db.session.flush()
            db.session.add(TaskParticipant(task_id=task.id, user_id=user.id, role="responsible"))
            leader = next(iter(students.values()))
            if user.id != leader.id:
                db.session.add(TaskParticipant(task_id=task.id, user_id=leader.id, role="collaborator"))
    ensure_web_programming_course()
    db.session.commit()


def ensure_web_programming_course():
    """Create the WEB04 Lập trình Web course with 30 groups and safe demo rosters.

    The demo keeps the existing eight accounts. Four student accounts are enrolled
    in this course and each is assigned to exactly one group; the remaining groups
    are intentionally empty so the instructor can demonstrate a 30-group class.
    """
    now_at = utcnow().replace(second=0, microsecond=0)
    coordinator = User.query.filter_by(email="coordinator@gmail.com").first()
    teacher = User.query.filter_by(email="gv2@gmail.com").first()
    students = [
        User.query.filter_by(email=f"sv{i}@gmail.com").first() for i in range(1, 5)
    ]
    if coordinator is None or teacher is None or any(u is None for u in students):
        return

    term = "2026–2027 / HK1"
    course = CourseOffering.query.filter_by(code="WEB04", term=term).first()
    if course is None:
        workspace = Workspace(
            name="WEB04",
            description="Không gian học phần Lập trình Web",
            owner_id=teacher.id,
        )
        db.session.add(workspace)
        db.session.flush()
        course = CourseOffering(
            code="WEB04",
            title="Lập trình Web",
            term=term,
            workspace_id=workspace.id,
            created_by=coordinator.id,
            status="active",
        )
        db.session.add(course)
        db.session.flush()
    else:
        # Keep an existing course's identity and data; only normalize its title/status.
        course.title = "Lập trình Web"
        course.status = "active"

    # Enroll the same existing users; no new accounts are created.
    for user, role in [(coordinator, "coordinator"), (teacher, "instructor")]:
        enrollment = CourseEnrollment.query.filter_by(
            course_id=course.id, user_id=user.id
        ).first()
        if enrollment is None:
            db.session.add(
                CourseEnrollment(
                    course_id=course.id, user_id=user.id, role=role, status="active"
                )
            )
        elif enrollment.status != "active":
            enrollment.status = "active"
            enrollment.role = role
        if not WorkspaceMember.query.filter_by(
            workspace_id=course.workspace_id, user_id=user.id
        ).first():
            db.session.add(
                WorkspaceMember(
                    workspace_id=course.workspace_id,
                    user_id=user.id,
                    role="owner" if role == "instructor" else "member",
                )
            )

    for index, user in enumerate(students, start=1):
        enrollment = CourseEnrollment.query.filter_by(
            course_id=course.id, user_id=user.id
        ).first()
        if enrollment is None:
            db.session.add(
                CourseEnrollment(
                    course_id=course.id,
                    user_id=user.id,
                    role="student",
                    status="active",
                    student_code=f"DEMO{index:03d}",
                )
            )
        elif enrollment.status != "active":
            enrollment.status = "active"
            enrollment.role = "student"
        if not WorkspaceMember.query.filter_by(
            workspace_id=course.workspace_id, user_id=user.id
        ).first():
            db.session.add(
                WorkspaceMember(
                    workspace_id=course.workspace_id,
                    user_id=user.id,
                    role="member",
                )
            )

    assignment = Assignment.query.filter_by(
        course_id=course.id, title="Xây dựng website thương mại điện tử mini"
    ).first()
    if assignment is None:
        assignment = Assignment(
            course_id=course.id,
            title="Xây dựng website thương mại điện tử mini",
            brief=(
                "Bài tập nhóm học phần Lập trình Web: phân tích yêu cầu, thiết kế giao diện, "
                "xây dựng frontend/backend, kiểm thử và hoàn thiện tài liệu triển khai."
            ),
            status="active",
            opens_at=now_at - timedelta(days=7),
            due_at=now_at + timedelta(days=35),
            group_min=1,
            group_max=5,
        )
        db.session.add(assignment)
        db.session.flush()

    # Create all 30 instructor-visible groups. The four existing student accounts
    # occupy G01-G04 (one group each); G05-G30 are available empty groups.
    groups = {}
    for number in range(1, 31):
        group_name = f"G{number:02d}"
        project = Project.query.filter_by(
            assignment_id=assignment.id, name=group_name
        ).first()
        if project is None:
            project = Project(
                workspace_id=course.workspace_id,
                name=group_name,
                description=(
                    f"Nhóm {group_name} – học phần Lập trình Web. "
                    + ("Đã có thành viên và công việc mẫu." if number <= 4 else "Nhóm chờ phân thành viên.")
                ),
                created_by=teacher.id,
                assignment_id=assignment.id,
                mode="academic",
                status="active",
            )
            db.session.add(project)
            db.session.flush()
        groups[number] = project

    # Assign each demo student to one and only one active group in this assignment.
    student_group = {}
    for number, user in enumerate(students, start=1):
        existing_membership = AssignmentMembership.query.filter_by(
            assignment_id=assignment.id, user_id=user.id, status="active"
        ).first()
        if existing_membership is None:
            db.session.add(
                AssignmentMembership(
                    assignment_id=assignment.id,
                    project_id=groups[number].id,
                    user_id=user.id,
                    role="leader",
                    status="active",
                )
            )
            existing_membership = db.session.query(AssignmentMembership).filter_by(
                assignment_id=assignment.id, user_id=user.id, status="active"
            ).one()
        student_group[user.id] = existing_membership.project_id
        if not ProjectMember.query.filter_by(
            project_id=existing_membership.project_id, user_id=user.id
        ).first():
            db.session.add(
                ProjectMember(
                    project_id=existing_membership.project_id,
                    user_id=user.id,
                    project_role="manager",
                )
            )

    # Seed realistic tasks only in groups that have a member, so every task has
    # a real responsible account and the remaining 26 groups stay available.
    task_specs = [
        ("Phân tích yêu cầu và user story", 1, 3, "in_progress", "high", 3),
        ("Thiết kế wireframe và giao diện", 1, 7, "todo", "medium", 2),
        ("Xây dựng cấu trúc HTML và CSS", 2, 5, "in_progress", "high", 3),
        ("Responsive giao diện trang chủ", 2, 10, "todo", "medium", 2),
        ("Thiết kế cơ sở dữ liệu", 3, 6, "todo", "high", 3),
        ("Xây dựng API và xử lý nghiệp vụ", 3, 13, "todo", "medium", 3),
        ("Kiểm thử chức năng đăng nhập", 4, 8, "review", "high", 2),
        ("Viết tài liệu hướng dẫn triển khai", 4, 16, "todo", "low", 1),
    ]
    for title, group_no, days, status, priority, points in task_specs:
        user = students[group_no - 1]
        project_id = student_group.get(user.id, groups[group_no].id)
        project = db.session.get(Project, project_id) or groups[group_no]
        if Task.query.filter_by(project_id=project.id, title=title).first():
            continue
        due = now_at + timedelta(days=days)
        task = Task(
            project_id=project.id,
            title=title,
            description=(
                f"Công việc demo của {project.name} trong bài tập Lập trình Web. "
                "Cập nhật tiến độ và đính kèm minh chứng khi hoàn thành."
            ),
            status=status,
            priority=priority,
            points=points,
            created_by=teacher.id,
            assignee_id=user.id,
            primary_assignee_id=user.id,
            due_at=due,
            original_due_at=due,
            created_at=(now_at - timedelta(days=2)).replace(tzinfo=None),
        )
        db.session.add(task)
        db.session.flush()
        db.session.add(
            TaskParticipant(task_id=task.id, user_id=user.id, role="responsible")
        )


def ensure_dashboard_demo_tasks():
    """Idempotently enrich an already-seeded demo database for dashboard UAT."""
    project = Project.query.filter_by(name="G01", mode="academic").first()
    if not project:
        return
    users = {key: User.query.filter_by(email=key + "@gmail.com").first() for key in ("sv1", "sv2", "sv3")}
    if any(user is None for user in users.values()):
        return
    # Do not re-add the previous oversized 12-task demo batch to WEB01.
    demo_tasks = []
    now_at = utcnow().replace(second=0, microsecond=0)
    old_demo_titles = {"Hoàn thiện bộ dữ liệu khảo sát", "Đối chiếu dữ liệu thiếu và ngoại lệ", "Thiết kế biểu đồ mô tả", "Viết phần phương pháp nghiên cứu", "Kiểm tra độ tin cậy thang đo", "Tổng hợp nhận xét của giảng viên", "Chuẩn hóa trích dẫn và tài liệu", "Rà soát định dạng báo cáo", "Chuẩn bị nội dung thuyết trình", "Tập dượt và ghi nhận góp ý", "Hoàn thiện phụ lục dữ liệu", "Nộp báo cáo cuối cùng"}
    for old_task in Task.query.filter_by(project_id=project.id).all():
        if old_task.title in old_demo_titles and old_task.status != "done":
            old_task.status = "done"
            old_task.completed_at = now_at.replace(tzinfo=None)
    existing = {title for (title,) in db.session.query(Task.title).filter_by(project_id=project.id).all()}
    for title, key, day_offset, status, priority, points in demo_tasks:
        if title in existing:
            continue
        due = now_at + timedelta(days=day_offset)
        task = Task(
            project_id=project.id,
            title=title,
            description="Công việc mẫu phục vụ kiểm thử quy trình phối hợp, deadline và cảnh báo của TeamSync.",
            status=status,
            priority=priority,
            points=points,
            created_by=users["sv1"].id,
            assignee_id=users[key].id,
            primary_assignee_id=users[key].id,
            due_at=due,
            original_due_at=due,
            created_at=(now_at - timedelta(days=5)).replace(tzinfo=None),
        )
        db.session.add(task)
        db.session.flush()
        db.session.add(TaskParticipant(task_id=task.id, user_id=users[key].id, role="responsible"))
        if key != "sv1":
            db.session.add(TaskParticipant(task_id=task.id, user_id=users["sv1"].id, role="collaborator"))
    if demo_tasks and len(existing) < len(demo_tasks):
        assignment = db.session.get(Assignment, project.assignment_id)
        if assignment and (not assignment.due_at or assignment.due_at < now_at + timedelta(days=25)):
            assignment.due_at = now_at + timedelta(days=30)
        for milestone in Milestone.query.filter_by(project_id=project.id).all():
            if milestone.title == "Dữ liệu và phân tích":
                milestone.due_at = now_at + timedelta(days=14)
            elif milestone.title == "Báo cáo cuối":
                milestone.due_at = now_at + timedelta(days=28)
    db.session.commit()


def update_demo_logins():
    """Update only named demo identities; never merge a conflicting Gmail account."""
    for key in ("ops", "coordinator", "gv1", "gv2", "sv1", "sv2", "sv3", "sv4"):
        old = User.query.filter_by(email=key + "@teamsync.local").first()
        current = User.query.filter_by(email=key + "@gmail.com").first()
        if old and current and old.id != current.id:
            raise ValueError("Demo email conflict: " + key + "@gmail.com")
        user = old or current
        if user:
            user.email = key + "@gmail.com"
            if key == "coordinator" and user.full_name in (
                "Điều phối học phần",
                "Điều phối viên",
            ):
                user.full_name = "Quản lý học phần"
            if not user.check_password(PASSWORD):
                user.set_password(PASSWORD)
    fixture = db.session.get(RuntimeSetting, "demo_fixture")
    if fixture:
        from .rubric import DEMO_CRITERIA

        aid = fixture.value["assignment_id"]
        policy = AssessmentPolicy.query.filter_by(
            assignment_id=aid, status="published"
        ).first()
        if policy:
            for item in DEMO_CRITERIA:
                c = Criterion.query.filter_by(
                    policy_id=policy.id, code=item["code"]
                ).first()
                if (
                    c
                    and c.description
                    == "Đánh giá từ sản phẩm, hồ sơ đóng góp và kiểm tra trực tiếp"
                ):
                    c.title, c.description, c.evidence_requirement = (
                        item["title"],
                        item["description"],
                        item["evidence_requirement"],
                    )
                    for level in CriterionLevel.query.filter_by(criterion_id=c.id):
                        if 0 <= level.ordinal < 4:
                            level.description = item["levels"][level.ordinal][
                                "description"
                            ]
    db.session.commit()
