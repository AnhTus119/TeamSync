import csv, io, hashlib, re, secrets
from flask import request, session, current_app
from ..academic import api
from ..academic.core import *
from ..models import Workspace, WorkspaceMember


@api.post("/auth/login")
def academic_login():
    from .api import login

    return login()


@api.post("/auth/logout")
def academic_logout():
    session.clear()
    return {"data": None}


@api.get("/auth/me")
@command()
def academic_me():
    u = current_user()
    return {
        **u.to_dict(),
        "enrollments": rows(CourseEnrollment, user_id=u.id),
        "business_time": iso(now()),
        "clock_mode": (
            "fixed"
            if current_app.config.get("DEMO_CLOCK_ENABLED")
            and (
                db.session.get(RuntimeSetting, "demo_clock")
                and db.session.get(RuntimeSetting, "demo_clock").value.get("at")
            )
            else "live"
        ),
        "demo_clock": __import__("flask").current_app.config.get(
            "DEMO_CLOCK_ENABLED", False
        ),
    }


@api.route("/courses", methods=["GET", "POST"])
@command()
def courses():
    if request.method == "GET":
        q = CourseOffering.query.join(
            CourseEnrollment, CourseEnrollment.course_id == CourseOffering.id
        ).filter(
            CourseEnrollment.user_id == current_user().id,
            CourseEnrollment.status == "active",
        )
        if request.args.get("term"):
            q = q.filter(CourseOffering.term == request.args["term"])
        return paginate(
            q.order_by(CourseOffering.id),
            lambda c: {**dto(c), "my_role": enrollment(c.id).role},
        )
    need(
        (current_user().role in ("instructor","coordinator") or CourseEnrollment.query.filter(CourseEnrollment.user_id==current_user().id, CourseEnrollment.role.in_(STAFF), CourseEnrollment.status=="active").first()),
        "FORBIDDEN",
        "Chỉ giảng viên được tạo lớp",
        403,
    )
    b = json_body()
    code = textval(b, "code")
    title = textval(b, "title")
    term = textval(b, "term")
    w = Workspace(name=code, description=title, owner_id=current_user().id)
    db.session.add(w)
    db.session.flush()
    db.session.add(
        WorkspaceMember(workspace_id=w.id, user_id=current_user().id, role="owner")
    )
    c = CourseOffering(
        code=code,
        title=title,
        term=term,
        workspace_id=w.id,
        created_by=current_user().id,
        status="active",
    )
    db.session.add(c)
    db.session.flush()
    db.session.add(
        CourseEnrollment(course_id=c.id, user_id=current_user().id, role="instructor")
    )
    audit("course.created", c, cid=c.id)
    return dto(c), 201


@api.route("/courses/<int:cid>", methods=["GET", "PATCH"])
@command()
def course_detail(cid):
    c = course(cid, coordinator=request.method == "PATCH")
    if request.method == "PATCH":
        b = json_body()
        version(c, b)
        for key in ("title", "term", "department_code"):
            if key in b:
                setattr(c, key, textval(b, key))
        audit("course.updated", c, cid=cid)
    return {**dto(c), "my_role": enrollment(cid).role}


@api.post("/courses/<int:cid>/archive")
@command()
def course_archive(cid):
    c = course(cid, coordinator=True)
    version(c)
    need(
        not Assignment.query.filter(
            Assignment.course_id == cid,
            Assignment.status.notin_(["closed", "archived"]),
        ).first(),
        "ACTIVE_ASSIGNMENTS_EXIST",
        "Còn đề bài chưa chốt trong lớp",
        409,
    )
    c.status = "archived"
    audit("course.archived", c, cid=cid)
    return dto(c)


@api.route("/courses/<int:cid>/enrollments", methods=["GET", "POST"])
@command()
def enrollments(cid):
    course(cid, staff=True)
    if request.method == "GET":
        return paginate(
            CourseEnrollment.query.filter_by(course_id=cid).order_by(
                CourseEnrollment.id
            ),
            lambda e: {**dto(e), "user": user_brief(e.user_id)},
        )
    b = json_body()
    role = b.get("role", "student")
    need(role in ("student", "instructor"))
    if role == "instructor":
        course(cid, coordinator=True)
        need(not CourseEnrollment.query.filter_by(course_id=cid,role="instructor",status="active").first(),message="Lớp đã có giảng viên phụ trách")
    email = textval(b, "email").lower()
    u = User.query.filter_by(email=email).first()
    need(u is not None, "NOT_FOUND", "Cần tạo tài khoản cục bộ trước", 404)
    need(u.role != "admin", "FORBIDDEN", "Ops không tham gia lớp học", 403)
    existing = CourseEnrollment.query.filter_by(course_id=cid, user_id=u.id).first()
    if existing:
        version(existing, b)
        existing.role = role
        existing.status = "active"
        existing.left_at = None
        e = existing
    else:
        e = CourseEnrollment(
            course_id=cid, user_id=u.id, role=role, student_code=b.get("student_code")
        )
        db.session.add(e)
    audit("enrollment.saved", e, cid=cid)
    return dto(e), 201


@api.post("/enrollments/<int:eid>/withdraw")
@command()
def withdraw(eid):
    e = get(CourseEnrollment, eid)
    course(e.course_id, staff=True)
    need(e.role == "student", "FORBIDDEN", "Chỉ quản lý sinh viên tại đây", 403)
    version(e)
    reason = textval(json_body(), "reason")
    e.status = "withdrawn"
    e.left_at = now()
    for m in AssignmentMembership.query.join(
        Assignment, Assignment.id == AssignmentMembership.assignment_id
    ).filter(
        Assignment.course_id == e.course_id,
        AssignmentMembership.user_id == e.user_id,
        AssignmentMembership.status == "active",
    ):
        m.status = "withdrawn"
        m.left_at = now()
    audit("enrollment.withdrawn", e, cid=e.course_id, reason=reason)
    return dto(e)


def validate_import_row(cid, data, seen_codes, seen_emails):
    errs = []
    code = data["student_code"]
    email = data["email"]
    if (
        not code
        or not data["full_name"]
        or not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email)
    ):
        errs.append("Thiếu mã/họ tên hoặc email sai định dạng")
    if code in seen_codes or email in seen_emails:
        errs.append("Mã sinh viên hoặc email trùng trong file")
    seen_codes.add(code)
    seen_emails.add(email)
    matches = CourseEnrollment.query.filter_by(student_code=code).all() if code else []
    if any(get(User, m.user_id).email != email for m in matches):
        errs.append("Mã sinh viên đã gắn với email khác")
    u = User.query.filter_by(email=email).first()
    if u:
        es = CourseEnrollment.query.filter_by(user_id=u.id).all()
        if not es or any(e.role != "student" or e.student_code != code for e in es):
            errs.append("Email đã gắn với tài khoản khác; không tự gộp")
    return errs


@api.post("/courses/<int:cid>/imports/preview")
@command()
def import_preview(cid):
    course(cid, staff=True)
    f = request.files.get("file")
    need(f is not None, message="Chọn file CSV UTF-8 hoặc Excel .xlsx")
    raw = f.read(2 * 1024 * 1024 + 1)
    need(len(raw) <= 2 * 1024 * 1024, "QUOTA_EXCEEDED", "CSV/Excel tối đa 2 MiB", 413)
    try:
        if (f.filename or '').lower().endswith('.xlsx'):
            from zipfile import ZipFile
            from openpyxl import load_workbook
            with ZipFile(io.BytesIO(raw)) as z:
                need(sum(x.file_size for x in z.infolist()) <= 20*1024*1024,
                    "QUOTA_EXCEEDED", "Excel giải nén tối đa 20 MiB", 413)
                need(not any(x.filename.lower().endswith('vbaproject.bin') for x in z.infolist()),message="Không chấp nhận macro")
            wb = load_workbook(io.BytesIO(raw),read_only=True,data_only=False)
            try:
                sheet=wb.active
                need(sheet.max_row <= 5001 and sheet.max_column <= 20, message="Excel tối đa 5.000 dòng, 20 cột")
                values=sheet.iter_rows(values_only=True)
                names=[str(v or '').strip() for v in next(values)]
                need(len(names)==len(set(names)) and {'student_code','full_name','email'}.issubset(names),
                     message="Cần cột student_code,full_name,email")
                items=[]
                for row in values:
                    if not any(v is not None for v in row): continue
                    need(not any(isinstance(v,str) and v.startswith('=') for v in row),message="Không chấp nhận công thức Excel")
                    items.append({k:str(v).strip() if v is not None else '' for k,v in zip(names,row)})
            finally:
                wb.close()
        else:
            reader = csv.DictReader(io.StringIO(raw.decode("utf-8-sig")))
            need(reader.fieldnames is not None and len(reader.fieldnames)==len(set(reader.fieldnames))
                 and {"student_code","full_name","email"}.issubset(reader.fieldnames),
                 message="Cần cột student_code,full_name,email")
            items=list(reader)
    except (UnicodeDecodeError,csv.Error,ValueError,StopIteration,KeyError, __import__('zipfile').BadZipFile):
        need(False,message="Không đọc được CSV/Excel hợp lệ")
    need(0 < len(items) <= 5000, message="CSV cần 1–5000 dòng")
    batch = ImportBatch(
        file_hash=hashlib.sha256(raw).hexdigest(),
        course_id=cid,
        mapping={
            "student_code": "student_code",
            "full_name": "full_name",
            "email": "email",
        },
        counts={},
        created_by=current_user().id,
    )
    db.session.add(batch)
    db.session.flush()
    codes = set()
    emails = set()
    nerr = 0
    for n, item in enumerate(items, 2):
        data = {
            k: (item.get(k) or "").strip()
            for k in ("student_code", "full_name", "email")
        }
        data["email"] = data["email"].lower()
        errs = validate_import_row(cid, data, codes, emails)
        nerr += bool(errs)
        db.session.add(
            ImportRow(
                batch_id=batch.id,
                row_no=n,
                normalized_json=data,
                errors_json=errs,
                action="conflict" if errs else "upsert",
            )
        )
    batch.counts = {"total": len(items), "errors": nerr}
    db.session.flush()
    return {**dto(batch), "rows": rows(ImportRow, batch_id=batch.id)}, 201


@api.get("/imports/<int:bid>")
@command()
def import_detail(bid):
    b = get(ImportBatch, bid)
    course(b.course_id, staff=True)
    return {**dto(b), "rows": rows(ImportRow, batch_id=bid)}


@api.post("/imports/<int:bid>/commit")
@command(idempotent=True)
def import_commit(bid):
    b = get(ImportBatch, bid, lock=True)
    course(b.course_id, staff=True)
    if b.status == "committed":
        return dto(b)
    version(b)
    need(
        not b.counts["errors"],
        "IMPORT_ERRORS",
        "Cần sửa các dòng lỗi trước khi nhập",
        409,
    )
    codes = set()
    emails = set()
    items = ImportRow.query.filter_by(batch_id=bid).order_by(ImportRow.id).all()
    for row in items:
        need(
            not validate_import_row(b.course_id, row.normalized_json, codes, emails),
            "IMPORT_CONFLICT",
            "Danh sách thay đổi sau preview; cần xem trước lại",
            409,
        )
    for row in items:
        d = row.normalized_json
        u = User.query.filter_by(email=d["email"]).first()
        if not u:
            u = User(email=d["email"], full_name=d["full_name"], role="user")
            u.set_password(
                "12345"
                if current_app.config.get("DEMO_CLOCK_ENABLED")
                else secrets.token_urlsafe(32)
            )
            db.session.add(u)
            db.session.flush()
        e = CourseEnrollment.query.filter_by(
            course_id=b.course_id, user_id=u.id
        ).first()
        if not e:
            e = CourseEnrollment(
                course_id=b.course_id,
                user_id=u.id,
                student_code=d["student_code"],
                role="student",
            )
            db.session.add(e)
        else:
            e.status = "active"
            e.left_at = None
        db.session.flush()
        row.committed_entity_id = e.id
    b.status = "committed"
    audit("import.committed", b, cid=b.course_id)
    return dto(b)


@api.get("/me/notifications")
@command()
def notifications():
    """List notifications; optional unread_only=true returns unread items only."""
    q = Notification.query.filter_by(recipient_id=current_user().id)
    if request.args.get("unread_only", "").lower() in ("1", "true", "yes"):
        q = q.filter(Notification.read_at.is_(None))
    return paginate(q.order_by(Notification.id.desc()))


@api.post("/notifications/<int:nid>/read")
@command()
def notification_read(nid):
    n = get(Notification, nid, lock=True)
    need(
        n.recipient_id == current_user().id,
        "NOT_FOUND",
        "Không tìm thấy thông báo",
        404,
    )
    # Mark-as-read is intentionally idempotent: opening an item that was
    # already read (for example in another tab) must not fail on an old version.
    if n.read_at is None:
        version(n)
        n.read_at = now()
    return dto(n)


@api.get("/admin/operations")
@command()
def operations():
    need(current_user().role == "admin", "FORBIDDEN", "Cần quyền vận hành", 403)
    return {
        "integrations": {"identity": "google_oidc" if current_app.config.get("GOOGLE_CLIENT_ID") else "disabled", "roster": "csv/xlsx", "grades": "csv/xlsx/pdf"},
        "pending_outbox": OutboxEvent.query.filter_by(processed_at=None).count(),
        "failed_jobs": OutboxEvent.query.filter(
            OutboxEvent.attempts > 0, OutboxEvent.processed_at == None
        ).count(),
        "retention": "Chưa được đơn vị chủ quản phê duyệt",
        "clock": iso(now()),
    }


@api.get("/me/overview")
@api.get("/me/deadlines")
@command()
def overview():
    uid = current_user().id

    # Collect every project the current user is entitled to see: active student
    # groups plus projects in courses where the user is an instructor/coordinator.
    student_project_ids = set(
        db.session.scalars(
            db.select(AssignmentMembership.project_id)
            .join(Assignment, Assignment.id == AssignmentMembership.assignment_id)
            .join(
                Project,
                db.and_(
                    Project.id == AssignmentMembership.project_id,
                    Project.assignment_id == Assignment.id,
                ),
            )
            .join(
                CourseEnrollment,
                db.and_(
                    CourseEnrollment.course_id == Assignment.course_id,
                    CourseEnrollment.user_id == AssignmentMembership.user_id,
                ),
            )
            .where(
                AssignmentMembership.user_id == uid,
                AssignmentMembership.status == "active",
                CourseEnrollment.status == "active",
                Assignment.status.notin_(["closed", "archived"]),
                Assignment.is_hidden.is_(False),
                Project.mode == "academic",
                Project.status.in_(["active", "assessment"]),
            )
        )
    )
    staff_courses = list(
        db.session.scalars(
            db.select(CourseEnrollment.course_id).where(
                CourseEnrollment.user_id == uid,
                CourseEnrollment.status == "active",
                CourseEnrollment.role.in_(STAFF),
            )
        )
    )
    staff_project_ids = set()
    if staff_courses:
        staff_project_ids = set(
            db.session.scalars(
                db.select(Project.id)
                .join(Assignment, Assignment.id == Project.assignment_id)
                .where(
                    Assignment.course_id.in_(staff_courses),
                    Assignment.status.notin_(["closed", "archived"]),
                    Project.mode == "academic",
                    Project.status.in_(["active", "assessment"]),
                )
            )
        )

    project_ids = student_project_ids | staff_project_ids
    project_info = {}
    if project_ids:
        project_rows = db.session.execute(
            db.select(Project.id, Project.name, Assignment.course_id, CourseOffering.code)
            .join(Assignment, Assignment.id == Project.assignment_id)
            .join(CourseOffering, CourseOffering.id == Assignment.course_id)
            .where(Project.id.in_(project_ids))
        ).all()
        project_info = {
            row.id: {"name": row.name, "course_id": row.course_id, "course_code": row.code}
            for row in project_rows
        }

    def open_task_query():
        if not project_ids:
            return []
        return (
            Task.query.join(Project, Project.id == Task.project_id)
            .join(Assignment, Assignment.id == Project.assignment_id)
            .filter(
                Task.project_id.in_(project_ids),
                Task.status != "done",
                Task.archived_at.is_(None),
                Project.status.in_(["active", "assessment"]),
                Assignment.status.notin_(["closed", "archived"]),
            )
            .order_by(Task.due_at.asc().nullslast(), Task.id.asc())
            .all()
        )

    group_tasks = open_task_query()
    task_ids = [t.id for t in group_tasks]
    task_participants = {}
    my_task_ids = set()
    if task_ids:
        participant_rows = db.session.execute(
            db.select(TaskParticipant.task_id, TaskParticipant.user_id, TaskParticipant.role, User.full_name)
            .join(User, User.id == TaskParticipant.user_id)
            .where(TaskParticipant.task_id.in_(task_ids))
        ).all()
        for row in participant_rows:
            task_participants.setdefault(row.task_id, []).append(
                {"id": row.user_id, "name": row.full_name, "role": row.role}
            )
            if row.user_id == uid:
                my_task_ids.add(row.task_id)

    # Keep /my-tasks personal while the dashboard also shows the entire group
    # workload (or the course workload for teaching staff).
    my_tasks = [t for t in group_tasks if t.id in my_task_ids]

    open_cases = []
    if project_ids:
        open_cases = (
            RiskCase.query.filter(
                RiskCase.project_id.in_(project_ids),
                RiskCase.status.notin_(["resolved", "dismissed"]),
            )
            .order_by(RiskCase.opened_at.asc())
            .all()
        )
    cases_by_task = {}
    for case in open_cases:
        if case.task_id:
            cases_by_task.setdefault(case.task_id, {})[case.rule_code] = case

    # Evaluate visible task facts at read time as well as using stored risk cases.
    # This prevents a just-triggered deadline/progress warning from waiting up to
    # the next background-worker cycle before it appears on the dashboard.
    from ..m17_reports.academic_services import risk_facts

    at = now()
    task_data = []
    task_data_by_id = {}
    computed_queue = []
    for t in group_tasks:
        rules = risk_facts(t, at)
        cases = cases_by_task.get(t.id, {})
        warnings = []
        for code, reason in rules.items():
            case = cases.get(code)
            warnings.append(
                {
                    "rule_code": code,
                    "severity": reason.get("severity", case.severity if case else "medium"),
                    "message": reason.get("message", "Công việc cần chú ý"),
                    "risk_case_id": case.id if case else None,
                    "path": f"/risk-cases/{case.id}" if case else f"/tasks/{t.id}",
                }
            )
            if case is None:
                computed_queue.append(
                    {
                        "title": reason.get("message", "Công việc cần chú ý") + ": " + t.title,
                        "path": f"/tasks/{t.id}",
                        "status": t.status,
                        "severity": reason.get("severity", "medium"),
                        "kind": "risk",
                        "at": iso(t.due_at),
                    }
                )
        # Retain an existing open case until the risk worker records its resolution.
        for code, case in cases.items():
            if not any(w["rule_code"] == code for w in warnings):
                warnings.append(
                    {
                        "rule_code": code,
                        "severity": case.severity,
                        "message": case.reason_json.get("message", "Công việc cần chú ý"),
                        "risk_case_id": case.id,
                        "path": f"/risk-cases/{case.id}",
                    }
                )
        info = project_info.get(t.project_id, {})
        participants = task_participants.get(t.id, [])
        responsible = next((x for x in participants if x["role"] == "responsible"), None)
        item = {
            "id": t.id,
            "project_id": t.project_id,
            "project_name": info.get("name", "Nhóm"),
            "course_id": info.get("course_id"),
            "course_code": info.get("course_code", ""),
            "title": t.title,
            "status": t.status,
            "due_at": iso(t.due_at),
            "points": t.points,
            "priority": t.priority,
            "assignee": responsible["name"] if responsible else "Chưa phân công",
            "participants": participants,
            "is_my_task": t.id in my_task_ids,
            "warnings": warnings,
        }
        task_data.append(item)
        task_data_by_id[t.id] = item

    queue = []
    for h in (
        HelpRequest.query.filter(
            HelpRequest.project_id.in_(staff_project_ids),
            HelpRequest.status.in_(["submitted", "under_review"]),
        )
        .order_by(HelpRequest.created_at.asc())
        .all()
        if staff_project_ids
        else []
    ):
        queue.append(
            {
                "title": "Yêu cầu trợ giúp: " + h.subject,
                "path": f"/projects/{h.project_id}?tab=help",
                "status": h.status,
                "severity": None,
                "kind": "help",
                "at": iso(h.created_at),
            }
        )
    for case in open_cases:
        queue.append(
            {
                "title": case.reason_json.get("message", "Công việc cần chú ý"),
                "path": f"/risk-cases/{case.id}",
                "status": case.status,
                "severity": case.severity,
                "kind": "risk",
                "at": iso(case.opened_at),
            }
        )
    # Add freshly computed alerts only when no persisted risk case exists yet.
    queue.extend(computed_queue)
    queue.sort(
        key=lambda item: (item.get("severity") != "high", item.get("at") or "")
    )

    return {
        "tasks": [task_data_by_id[t.id] for t in my_tasks],
        "group_tasks": task_data,
        "action_queue": queue,
        "notifications": Notification.query.filter_by(
            recipient_id=uid, read_at=None
        ).count(),
        "time": iso(at),
    }


@api.get("/courses/<int:cid>/overview")
@command()
def course_overview(cid):
    c = course(cid, staff=True)
    aids = db.select(Assignment.id).where(Assignment.course_id == cid)
    pids = db.select(Project.id).where(Project.assignment_id.in_(aids))
    return {
        "course": dto(c),
        "projects": Project.query.filter(Project.assignment_id.in_(aids)).count(),
        "risk_cases": RiskCase.query.filter(
            RiskCase.project_id.in_(pids),
            RiskCase.status.notin_(["resolved", "dismissed"]),
        ).count(),
        "pending_reviews": TaskSubmission.query.join(
            Task, Task.id == TaskSubmission.task_id
        )
        .filter(Task.project_id.in_(pids), TaskSubmission.status == "pending")
        .count(),
    }


@api.route("/admin/users", methods=["GET", "POST"])
@command()
def account_admin():
    need(
        current_user().role == "admin", "FORBIDDEN", "Cần quyền quản trị tài khoản", 403
    )
    if request.method == "GET":
        return paginate(User.query.order_by(User.id), lambda u: u.to_dict())
    b = json_body()
    email = textval(b, "email").lower()
    need(
        re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email) is not None,
        message="Email không hợp lệ",
    )
    password = textval(
        b, "password", 5 if current_app.config.get("DEMO_CLOCK_ENABLED") else 12
    )
    role = b.get("role", "user")
    need(role in ("user", "instructor", "coordinator"))
    u = User(email=email, full_name=textval(b, "full_name"), role=role)
    u.set_password(password)
    db.session.add(u)
    audit("account.created", u)
    return u.to_dict(), 201


@api.post("/admin/users/<int:uid>/password")
@command()
def account_password(uid):
    need(
        current_user().role == "admin", "FORBIDDEN", "Cần quyền quản trị tài khoản", 403
    )
    user = get(User, uid)
    password = textval(
        json_body(),
        "password",
        5 if current_app.config.get("DEMO_CLOCK_ENABLED") else 12,
    )
    user.set_password(password)
    audit("account.password_reset", user)
    return {"id": user.id, "updated": True}


@api.post('/courses/<int:cid>/students')
@command()
def create_course_student(cid):
    course(cid, staff=True)
    b = json_body()
    data = {k: textval(b, k) for k in ('student_code', 'full_name', 'email')}
    data['email'] = data['email'].lower()
    errors = validate_import_row(cid, data, set(), set())
    need(not errors, message='; '.join(errors))
    u = User.query.filter_by(email=data['email']).first()
    if not u:
        u = User(email=data['email'], full_name=data['full_name'], role='user')
        u.set_password(secrets.token_urlsafe(32))
        db.session.add(u)
        db.session.flush()
    need(not CourseEnrollment.query.filter_by(course_id=cid, user_id=u.id).first(), message='Sinh viên đã có trong lớp')
    e = CourseEnrollment(course_id=cid, user_id=u.id, student_code=data['student_code'], role='student')
    db.session.add(e)
    db.session.flush()
    audit('enrollment.created', e, cid=cid)
    return dto(e), 201


@api.patch('/enrollments/<int:eid>')
@command()
def update_course_student(eid):
    e = get(CourseEnrollment, eid)
    course(e.course_id, staff=True)
    need(e.role == 'student', 'FORBIDDEN', 'Chỉ chỉnh sửa sinh viên', 403)
    b = json_body()
    version(e, b)
    name, code = textval(b, 'full_name'), textval(b, 'student_code')
    need(not CourseEnrollment.query.filter(CourseEnrollment.student_code == code, CourseEnrollment.user_id != e.user_id).first(), message='Mã sinh viên đã được sử dụng')
    get(User, e.user_id).full_name = name
    e.student_code = code
    audit('enrollment.updated', e, cid=e.course_id)
    return dto(e)
