"""Student invitations, contribution decisions, quality reviews and group reports."""

from io import BytesIO
from decimal import Decimal, ROUND_HALF_UP
from flask import request, send_file, render_template, current_app
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.utils.exceptions import InvalidFileException
from xml.etree.ElementTree import ParseError
from zipfile import BadZipFile, ZipFile
from . import api
from .core import *
from ..m06_projects.academic_api import add_group_member


def mentor_ids(pid):
    p=get(Project,pid)
    return [e.user_id for e in CourseEnrollment.query.filter_by(course_id=get(Assignment,p.assignment_id).course_id,role="instructor",status="active")]


def require_mentor(pid):
    need(
        current_user().id in mentor_ids(pid),
        "MENTOR_REQUIRED",
        "Cần giảng viên phụ trách lớp",
        403,
    )


def contact_brief(uid):
    return {**user_brief(uid), "email": get(User, uid).email}


def invitation_dto(x):
    p = get(Project, x.project_id)
    return {
        **dto(x),
        "user": contact_brief(x.user_id),
        "project_name": p.name,
        "assignment_id": p.assignment_id,
    }


@api.get("/me/invitations")
@command()
def my_invitations():
    return paginate(
        GroupInvitation.query.filter_by(user_id=current_user().id).order_by(
            GroupInvitation.id.desc()
        ),
        invitation_dto,
    )


@api.get("/projects/<int:pid>/invitations")
@command()
def group_invitations(pid):
    project(pid)
    return paginate(
        GroupInvitation.query.filter_by(project_id=pid).order_by(GroupInvitation.id),
        invitation_dto,
    )


@api.get("/assignments/<int:aid>/invite-candidates")
@command()
def invite_candidates(aid):
    a = assignment(aid)
    assigned = {
        m.user_id
        for m in AssignmentMembership.query.filter_by(
            assignment_id=aid, status="active"
        )
    }
    return {
        "students": [
            contact_brief(e.user_id)
            for e in CourseEnrollment.query.filter_by(
                course_id=a.course_id, status="active", role="student"
            )
            if e.user_id not in assigned
        ],
        "instructors": [
            contact_brief(e.user_id)
            for e in CourseEnrollment.query.filter_by(
                course_id=a.course_id, status="active", role="instructor"
            )
        ],
    }


@api.post("/projects/<int:pid>/invitations")
@command(idempotent=True)
def invite_to_group(pid):
    p = project(pid, mutable=True)
    state(p,["draft"])
    m = membership(pid)
    need(m and m.role == "leader", "FORBIDDEN", "Nhóm trưởng gửi lời mời", 403)
    version(p)
    b = json_body()
    uid, kind = integer(b.get("user_id")), b.get("kind")
    a = get(Assignment, p.assignment_id)
    e = enrollment(a.course_id, uid)
    need(
        kind == "member"
        and e
        and e.role == ("student" if kind == "member" else "instructor"),
        "INVALID_PARTICIPANT",
        "Người được mời phải thuộc lớp học phần",
    )
    if kind == "member":
        from ..collab.organization import require_self_formation
        require_self_formation(a)
        need(
            not AssignmentMembership.query.filter_by(
                assignment_id=a.id, user_id=uid, status="active"
            ).first(),
            "MEMBERSHIP_CONFLICT",
            "Sinh viên đã có nhóm",
            409,
        )
    else:
        need(
            AssignmentMembership.query.filter_by(
                project_id=pid, status="active"
            ).count()
            >= a.group_min,
            "GROUP_SIZE_INVALID",
            "Cần đủ thành viên xác nhận trước khi mời giảng viên",
            409,
        )
    inv = GroupInvitation.query.filter_by(project_id=pid, user_id=uid).first()
    need(
        not inv or inv.status == "rejected",
        "INVITATION_EXISTS",
        "Lời mời đang chờ hoặc đã được chấp nhận",
        409,
    )
    if not inv:
        inv = GroupInvitation(
            project_id=pid, user_id=uid, invited_by=current_user().id, kind=kind
        )
        db.session.add(inv)
    else:
        inv.status, inv.responded_at, inv.invited_by = (
            "pending",
            None,
            current_user().id,
        )
    audit("group.invited", inv, pid=pid)
    notify("group.invited", inv, [uid], "/notifications")
    return invitation_dto(inv), 201


@api.post("/invitations/<int:iid>/respond")
@command(idempotent=True)
def invitation_respond(iid):
    inv = get(GroupInvitation, iid, lock=True)
    need(inv.user_id == current_user().id, "NOT_FOUND", "Không tìm thấy lời mời", 404)
    version(inv)
    state(inv, ["pending"])
    action = json_body().get("action")
    need(action in ("accept", "reject"))
    p = get(Project, inv.project_id, lock=True)
    a = assignment(p.assignment_id)
    need(
        p.status == "draft"
        and a.status in ("published", "active"),
        "FINALIZED_LOCKED",
        "Nhóm không còn nhận thành viên",
        409,
    )
    expected_role = "student" if inv.kind == "member" else "instructor"
    need(
        enrollment(a.course_id).role == expected_role,
        "FORBIDDEN",
        "Vai trò trong lớp đã thay đổi",
        403,
    )
    if action == "accept" and inv.kind == "member":
        from ..collab.organization import require_self_formation
        require_self_formation(a)
        add_group_member(p, inv.user_id, "member")
        p.version += 1
    inv.status, inv.responded_at = (
        "accepted" if action == "accept" else "rejected"
    ), now()
    audit("group.invitation_" + inv.status, inv, pid=p.id)
    leaders = [
        m.user_id
        for m in AssignmentMembership.query.filter_by(
            project_id=p.id, status="active", role="leader"
        )
    ]
    notify("group.invitation_responded", inv, leaders, f"/projects/{p.id}?tab=settings")
    return invitation_dto(inv)


def shares_for_task(t):
    s = (
        db.session.get(TaskSubmission, t.latest_submission_id)
        if t.latest_submission_id
        else None
    )
    ids = sorted(
        s.participant_ids
        if s
        else [x.user_id for x in TaskParticipant.query.filter_by(task_id=t.id)]
    )
    latest = (
        AllocationChange.query.filter_by(task_id=t.id)
        .order_by(AllocationChange.id.desc())
        .first()
    )
    if latest and {int(k) for k in latest.shares} == set(ids):
        return latest.shares
    if not ids:
        return {}
    share = (Decimal(100) / len(ids)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    values = {str(uid): str(share) for uid in ids}
    values[str(ids[0])] = str(Decimal(100) - share * (len(ids) - 1))
    return values


def complaint_dto(c):
    t = get(Task, c.task_id)
    return {
        **dto(c),
        "task_title": t.title,
        "raised_by_name": user_brief(c.raised_by)["full_name"],
        "target_name": user_brief(c.target_id)["full_name"],
        "shares": shares_for_task(t),
        "participants": [
            {"user": user_brief(x.user_id)}
            for x in TaskParticipant.query.filter_by(task_id=t.id)
        ],
        "changes": rows(AllocationChange, complaint_id=c.id),
    }


@api.route("/projects/<int:pid>/complaints", methods=["GET", "POST"])
@command(idempotent=True)
def work_complaints(pid):
    p = project(pid, mutable=request.method == "POST")
    if request.method == "GET":
        need(not is_staff(p),"FORBIDDEN","Dùng danh sách hỗ trợ được chuyển tới giảng viên",403)
        return paginate(
            WorkComplaint.query.join(Task)
            .filter(Task.project_id == pid)
            .order_by(WorkComplaint.id.desc()),
            complaint_dto,
        )
    b = json_body()
    t = task(integer(b.get("task_id")))
    need(t.project_id == pid)
    participant(t)
    target = integer(b.get("target_id"))
    need(
        target != current_user().id
        and TaskParticipant.query.filter_by(task_id=t.id, user_id=target).first(),
        "INVALID_PARTICIPANT",
        "Chỉ phản ánh người cùng được phân công",
    )
    need(
        t.latest_submission_id,
        "SUBMISSION_REQUIRED",
        "Cần có bản nộp để đối chiếu đóng góp",
        409,
    )
    need(
        not WorkComplaint.query.filter_by(
            task_id=t.id, target_id=target, raised_by=current_user().id, status="open"
        ).first(),
        "COMPLAINT_EXISTS",
        "Phản ánh đang được xử lý",
        409,
    )
    leader = AssignmentMembership.query.filter_by(
        project_id=pid, role="leader", status="active"
    ).first()
    need(leader, "LEADER_REQUIRED", "Nhóm cần trưởng nhóm", 409)
    teacher_case = target == leader.user_id or current_user().id == leader.user_id
    recipients = mentor_ids(pid) if teacher_case else [leader.user_id]
    need(
        not teacher_case or recipients,
        "MENTOR_REQUIRED",
        "Cần giảng viên chấp nhận lời mời để xử lý phản ánh liên quan trưởng nhóm",
        409,
    )
    c = WorkComplaint(
        task_id=t.id,
        raised_by=current_user().id,
        target_id=target,
        reason=textval(b, "reason"),
        handler="instructor" if teacher_case else "leader",
    )
    db.session.add(c)
    audit("contribution.complained", c, pid=pid)
    notify(
        "help.complaint" if teacher_case else "contribution.complained",
        c,
        recipients + [target],
        f"/projects/{pid}?tab=contributions",
    )
    return complaint_dto(c), 201


@api.post("/complaints/<int:cid>/explain")
@command()
def complaint_explain(cid):
    c = get(WorkComplaint, cid, lock=True)
    t = task(c.task_id, mutable=True)
    need(
        c.target_id == current_user().id,
        "FORBIDDEN",
        "Chỉ thành viên được phản ánh gửi giải trình",
        403,
    )
    state(c, ["open"])
    version(c)
    c.explanation = textval(json_body(), "explanation")
    audit("contribution.explained", c, pid=t.project_id, reason=c.explanation)
    return complaint_dto(c)


@api.post("/complaints/<int:cid>/escalate")
@command(idempotent=True)
def complaint_escalate(cid):
    c = get(WorkComplaint, cid, lock=True)
    t = task(c.task_id, mutable=True)
    m = membership(t.project_id)
    need(
        m and (m.role == "leader" or current_user().id in (c.raised_by, c.target_id)),
        "FORBIDDEN",
        "Chỉ người liên quan hoặc trưởng nhóm chuyển yêu cầu",
        403,
    )
    state(c, ["open"])
    version(c)
    need(
        c.handler == "leader", "INVALID_TRANSITION", "Yêu cầu đã chuyển giảng viên", 409
    )
    teachers = mentor_ids(t.project_id)
    need(teachers, "MENTOR_REQUIRED", "Cần giảng viên chấp nhận lời mời", 409)
    c.handler, c.escalation_reason = "instructor", textval(json_body(), "reason")
    audit("contribution.escalated", c, pid=t.project_id, reason=c.escalation_reason)
    notify("help.complaint", c, teachers, f"/projects/{t.project_id}?tab=contributions")
    return complaint_dto(c)


@api.post("/complaints/<int:cid>/resolve")
@command(idempotent=True)
def complaint_resolve(cid):
    c = get(WorkComplaint, cid, lock=True)
    t = task(c.task_id, mutable=True)
    m = membership(t.project_id)
    if c.handler == "instructor":
        require_mentor(t.project_id)
    else:
        need(
            m
            and m.role == "leader"
            and current_user().id not in (c.raised_by, c.target_id),
            "FORBIDDEN",
            "Trưởng nhóm không tự xử lý phản ánh liên quan mình",
            403,
        )
    state(c, ["open"])
    version(c)
    b = json_body()
    need(
        bool(c.explanation) or b.get("explanation_not_provided") is True,
        "EXPLANATION_REQUIRED",
        "Chờ giải trình hoặc xác nhận đã cho thành viên cơ hội giải trình",
        409,
    )
    reason = textval(b, "reason")
    values = b.get("shares")
    expected = set(shares_for_task(t))
    need(
        isinstance(values, dict) and set(values) == expected,
        "INVALID_ALLOCATION",
        "Tỷ lệ phải gồm đúng những người được ghi nhận",
    )
    values = {key: decimal(value) for key, value in values.items()}
    need(
        sum(values.values()) == 100,
        "INVALID_ALLOCATION",
        "Tổng tỷ lệ đóng góp phải bằng 100%",
    )
    c.status, c.resolution, c.resolved_by, c.resolved_at = (
        "resolved",
        reason,
        current_user().id,
        now(),
    )
    db.session.add(
        AllocationChange(
            task_id=t.id,
            complaint_id=c.id,
            decided_by=current_user().id,
            shares={k: str(v) for k, v in values.items()},
            reason=reason,
        )
    )
    audit("contribution.resolved", c, pid=t.project_id, reason=reason)
    notify(
        "contribution.resolved",
        c,
        [
            x.user_id
            for x in AssignmentMembership.query.filter_by(
                project_id=t.project_id, status="active"
            )
        ],
        f"/projects/{t.project_id}?tab=contributions",
    )
    db.session.flush()
    return complaint_dto(c)


@api.post("/projects/<int:pid>/quality")
@command()
def quality_review(pid):
    p = project(pid, mutable=True)
    m = membership(pid)
    need(
        m and m.role == "leader",
        "FORBIDDEN",
        "Nhóm trưởng đánh giá chất lượng sản phẩm",
        403,
    )
    version(p)
    b = json_body()
    c = get(Criterion, integer(b.get("criterion_id")))
    need(
        c.policy_id == get(Assignment, p.assignment_id).published_policy_id,
        "INVALID_CRITERION",
        "Tiêu chí không thuộc đề bài",
    )
    level = get(CriterionLevel, integer(b.get("level_id")))
    need(
        level.criterion_id == c.id,
        "INVALID_CRITERION",
        "Mức đánh giá không thuộc tiêu chí",
    )
    value = QualityEvaluation.query.filter_by(project_id=pid, criterion_id=c.id).first()
    if not value:
        value = QualityEvaluation(project_id=pid, criterion_id=c.id)
        db.session.add(value)
    value.level_id, value.rationale, value.evaluated_by = (
        level.id,
        textval(b, "rationale"),
        current_user().id,
    )
    audit("quality.evaluated", value, pid=pid, reason=value.rationale)
    return dto(value)


def group_report(p):
    a = get(Assignment, p.assignment_id)
    tasks = Task.query.filter_by(project_id=p.id).order_by(Task.id).all()
    members = AssignmentMembership.query.filter_by(
        project_id=p.id
    ).all()
    totals = {m.user_id: Decimal(0) for m in members}
    work = []
    for t in tasks:
        d = task_dto(t)
        shares = shares_for_task(t)
        d["shares"] = [
            {"user": user_brief(int(uid)), "percent": percent}
            for uid, percent in shares.items()
        ]
        if t.status == "done":
            for uid, percent in shares.items():
                totals.setdefault(int(uid), Decimal(0))
                totals[int(uid)] += Decimal(t.points) * Decimal(percent) / 100
        work.append(d)
    total = sum(totals.values())
    quality = []
    for c in Criterion.query.filter_by(policy_id=a.published_policy_id).order_by(
        Criterion.id
    ):
        v = QualityEvaluation.query.filter_by(
            project_id=p.id, criterion_id=c.id
        ).first()
        quality.append(
            {
                "criterion": dto(c),
                "levels": rows(CriterionLevel, criterion_id=c.id),
                "evaluation": dto(v) if v else None,
                "level_label": (
                    get(CriterionLevel, v.level_id).label if v else "Chưa đánh giá"
                ),
            }
        )
    return {
        "project": dto(p),
        "assignment": dto(a),
        "generated_at": iso(now()),
        "tasks": work,
        "quality": quality,
        "members": [
            {
                "user": contact_brief(uid),
                "accepted_workload": str(value.quantize(Decimal(".01"))),
                "percent": (
                    str((value * 100 / total).quantize(Decimal(".01")))
                    if total
                    else "0"
                ),
            }
            for uid, value in totals.items()
        ],
        "complaints": [] if is_staff(p) else [
            complaint_dto(c)
            for c in WorkComplaint.query.join(Task)
            .filter(Task.project_id == p.id)
            .order_by(WorkComplaint.id)
        ],
        "allocation_history": [] if is_staff(p) else [
            {**dto(x), "decided_by_name": user_brief(x.decided_by)["full_name"]}
            for x in AllocationChange.query.join(Task)
            .filter(Task.project_id == p.id)
            .order_by(AllocationChange.id)
        ],
    }


@api.get("/projects/<int:pid>/report")
@command()
def report_detail(pid):
    return group_report(project(pid))


@api.get("/projects/<int:pid>/report/download")
def report_download(pid):
    need(current_user() is not None, "UNAUTHORIZED", "Bạn cần đăng nhập", 401)
    data = group_report(project(pid))
    if request.args.get("format") == "xlsx":
        wb = Workbook()
        ws = wb.active
        ws.title = "Đóng góp"
        ws.append(["Thành viên", "Email", "Khối lượng đã duyệt", "Tỷ trọng đóng góp %"])
        for m in data["members"]:
            ws.append(
                [
                    excel_text(m["user"]["full_name"]),
                    excel_text(m["user"]["email"]),
                    float(m["accepted_workload"]),
                    float(m["percent"]),
                ]
            )
        ws = wb.create_sheet("Công việc")
        ws.append(["Công việc", "Trạng thái", "Khối lượng", "Phân bổ đóng góp"])
        for t in data["tasks"]:
            ws.append(
                [
                    excel_text(t["title"]),
                    t["status"],
                    t["points"],
                    excel_text(
                        "; ".join(
                            x["user"]["full_name"] + ": " + x["percent"] + "%"
                            for x in t["shares"]
                        )
                    ),
                ]
            )
        ws = wb.create_sheet("Chất lượng")
        ws.append(["Tiêu chí", "Mức đánh giá", "Nhận xét"])
        for q in data["quality"]:
            ws.append(
                [
                    excel_text(q["criterion"]["title"]),
                    excel_text(q["level_label"]),
                    excel_text((q["evaluation"] or {}).get("rationale", "")),
                ]
            )
        ws = wb.create_sheet("Khiếu nại")
        ws.append(
            [
                "Công việc",
                "Người phản ánh",
                "Thành viên",
                "Nội dung",
                "Giải trình",
                "Trạng thái",
                "Kết luận",
            ]
        )
        for c in data["complaints"]:
            ws.append(
                [
                    excel_text(c.get(k) or "")
                    for k in (
                        "task_title",
                        "raised_by_name",
                        "target_name",
                        "reason",
                        "explanation",
                        "status",
                        "resolution",
                    )
                ]
            )
        return workbook_download(wb, f"TeamSync-nhom-{pid}.xlsx")
    html = render_template("academic/report.html", report=data)
    response = current_app.response_class(html, mimetype="text/html")
    response.headers["Content-Disposition"] = (
        f'attachment; filename="TeamSync-nhom-{pid}.html"'
    )
    return response


def excel_text(value):
    value = str(value)
    return "'" + value if value.lstrip().startswith(("=", "+", "-", "@")) else value


def workbook_download(wb, filename):
    for sheet in wb:
        sheet.freeze_panes = "A2"
        sheet.auto_filter.ref = sheet.dimensions
        for cell in sheet[1]:
            cell.font = Font(bold=True, color="FFFFFF")
            cell.fill = PatternFill("solid", fgColor="245ED6")
        for column in sheet.columns:
            sheet.column_dimensions[column[0].column_letter].width = min(
                60, max(18, max(len(str(c.value or "")) for c in column) + 2)
            )
            for cell in column:
                cell.alignment = Alignment(vertical="top", wrap_text=True)
    out = BytesIO()
    wb.save(out)
    out.seek(0)
    return send_file(
        out,
        as_attachment=True,
        download_name=filename,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


RUBRIC_HEADERS = [
    "Mã",
    "Tiêu chí",
    "Mô tả",
    "Trọng số %",
    "Minh chứng cần có",
    "Chưa đạt",
    "Đạt",
    "Tốt",
    "Xuất sắc",
]


@api.get("/assignments/<int:aid>/rubric-template")
def rubric_template(aid):
    need(current_user() is not None, "UNAUTHORIZED", "Bạn cần đăng nhập", 401)
    assignment(aid, staff=True)
    wb = Workbook()
    ws = wb.active
    ws.title = "Tiêu chí"
    ws.append(RUBRIC_HEADERS)
    from .rubric import DEMO_CRITERIA

    for c in DEMO_CRITERIA:
        ws.append(
            [
                c["code"],
                c["title"],
                c["description"],
                c["weight"],
                c["evidence_requirement"],
                *[x["description"] for x in c["levels"]],
            ]
        )
    ws.freeze_panes = "A2"
    for column in ws.columns:
        ws.column_dimensions[column[0].column_letter].width = 35
    return workbook_download(wb, "TeamSync-mau-tieu-chi.xlsx")


@api.post("/assignments/<int:aid>/rubric-preview")
@command()
def rubric_preview(aid):
    a = assignment(aid, staff=True)
    state(a, ["draft"])
    f = request.files.get("file")
    need(
        f and f.filename.lower().endswith(".xlsx"),
        "INVALID_FILE",
        "Chọn file Excel .xlsx",
    )
    raw = f.read(2 * 1024 * 1024 + 1)
    need(len(raw) <= 2 * 1024 * 1024, "FILE_TOO_LARGE", "File mẫu tối đa 2 MiB", 413)
    try:
        with ZipFile(BytesIO(raw)) as archive:
            need(
                sum(x.file_size for x in archive.infolist()) <= 12 * 1024 * 1024,
                "INVALID_FILE",
                "File Excel vượt giới hạn giải nén",
            )
        wb = load_workbook(
            BytesIO(raw), read_only=True, data_only=False, keep_links=False
        )
        sheet = wb.active
        rows = list(sheet.iter_rows(max_row=32, max_col=9, values_only=True))
        need(
            list(rows[0]) == RUBRIC_HEADERS,
            "INVALID_TEMPLATE",
            "Sai cột mẫu; hãy tải mẫu từ hệ thống",
        )
        items = []
        for row in rows[1:]:
            if not any(v is not None for v in row):
                continue
            need(
                all(v is not None and str(v).strip() for v in row),
                "INVALID_TEMPLATE",
                "Mọi ô trong dòng tiêu chí đều bắt buộc",
            )
            need(
                not any(isinstance(v, str) and v.startswith("=") for v in row),
                "INVALID_TEMPLATE",
                "Không dùng công thức trong mẫu tiêu chí",
            )
            items.append(
                {
                    "code": str(row[0]).strip(),
                    "title": str(row[1]).strip(),
                    "description": str(row[2]).strip(),
                    "weight": str(decimal(row[3], 0.01)),
                    "evidence_requirement": str(row[4]).strip(),
                    "levels": [
                        {
                            "label": label,
                            "score": score,
                            "description": str(row[i + 5]).strip(),
                        }
                        for i, (label, score) in enumerate(
                            [("Chưa đạt", 0), ("Đạt", 5), ("Tốt", 8), ("Xuất sắc", 10)]
                        )
                    ],
                }
            )
        need(
            1 <= len(items) <= 30 and len({x["code"] for x in items}) == len(items),
            "INVALID_TEMPLATE",
            "Cần 1–30 tiêu chí và mã không trùng",
        )
        need(
            sum(Decimal(x["weight"]) for x in items) == 100,
            "WEIGHTS_INVALID",
            "Tổng trọng số phải bằng 100%",
        )
        wb.close()
    except (
        BadZipFile,
        ValueError,
        KeyError,
        IndexError,
        TypeError,
        InvalidFileException,
        ParseError,
    ):
        need(
            False,
            "INVALID_FILE",
            "Không đọc được file Excel; hãy sử dụng đúng file mẫu",
        )
    return {"criteria": items, "assignment_id": aid, "status": "previewed"}
