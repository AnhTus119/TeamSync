from flask import request
from ..academic import api
from ..academic.core import *
from .academic_services import risk_facts, evaluate_project


@api.get("/courses/<int:cid>/risk-cases")
@command()
def risks(cid):
    course(cid)
    aids = db.select(Assignment.id).where(Assignment.course_id == cid)
    if enrollment(cid).role not in STAFF:
        aids = aids.where(Assignment.is_hidden.is_(False))
    q = RiskCase.query.join(Project, Project.id == RiskCase.project_id).filter(
        Project.assignment_id.in_(aids)
    )
    if enrollment(cid).role not in STAFF:
        pids = db.select(AssignmentMembership.project_id).where(
            AssignmentMembership.user_id == current_user().id,
            AssignmentMembership.status == "active",
        )
        q = q.filter(RiskCase.project_id.in_(pids))
    if request.args.get("status"):
        q = q.filter(RiskCase.status == request.args["status"])
    return paginate(
        q.order_by(RiskCase.opened_at),
        lambda c: {**dto(c), "owner": user_brief(c.owner_id) if c.owner_id else None},
    )


@api.get("/risk-cases/<int:rid>")
@command()
def risk_detail(rid):
    c = get(RiskCase, rid)
    project(c.project_id)
    return {
        **dto(c),
        "owner": user_brief(c.owner_id) if c.owner_id else None,
        "actions": rows(InterventionAction, risk_case_id=rid),
    }


@api.post("/risk-cases/<int:rid>/acknowledge")
@api.post("/risk-cases/<int:rid>/actions")
@api.post("/risk-cases/<int:rid>/resolve")
@api.post("/risk-cases/<int:rid>/dismiss")
@command()
def risk_command(rid):
    c = get(RiskCase, rid, lock=True)
    p = project(c.project_id, mutable=True)
    version(c)
    b = json_body()
    op = request.path.rsplit("/", 1)[1]
    need(
        (membership(p.id) and membership(p.id).role == "leader"),
        "FORBIDDEN",
        "Chỉ người phụ trách hoặc người điều phối xử lý",
        403,
    )
    state(c, ["new", "acknowledged", "action_planned", "monitoring"])
    content = textval(b, "content")
    if op == "acknowledge":
        c.status = "acknowledged"
        c.owner_id = current_user().id
    elif op == "actions":
        c.status = (
            "action_planned" if b.get("action_type") != "monitoring" else "monitoring"
        )
        c.next_review_at = timestamp(b.get("due_at"))
    elif op == "dismiss":
        need(membership(p.id) and membership(p.id).role == "leader", "FORBIDDEN", "Chỉ nhóm trưởng mới được bỏ qua cảnh báo", 403)
        c.status = "dismissed"
        c.next_review_at = timestamp(b.get("next_review_at"))
        need(c.next_review_at > now())
    elif op == "resolve":
        # Re-evaluate facts; a label change cannot override an ongoing risk.
        if c.task_id:
            need(
                c.rule_code not in risk_facts(get(Task, c.task_id), now()),
                "RISK_STILL_ACTIVE",
                "Điều kiện cảnh báo vẫn còn; cần cập nhật kế hoạch",
                409,
            )
        else:
            evaluate_project(p)
            need(
                c.status == "resolved",
                "RISK_STILL_ACTIVE",
                "Điều kiện cảnh báo vẫn còn",
                409,
            )
        c.status = "resolved"
        c.resolved_at = now()
    db.session.add(
        InterventionAction(
            risk_case_id=rid,
            actor_id=current_user().id,
            action_type=op,
            content=content,
            due_at=c.next_review_at,
            completed_at=now() if op in ("resolve", "dismiss") else None,
        )
    )
    audit("risk." + op, c, pid=p.id)
    return dto(c)


@api.post("/courses/<int:cid>/risk-evaluate")
@command()
def risk_evaluate(cid):
    course(cid, staff=True)
    from ..common.jobs import risk_lock

    with risk_lock() as acquired:
        need(acquired, "JOB_BUSY", "Đã có lượt kiểm tra đang chạy", 409)
        count = 0
        for p in Project.query.join(
            Assignment, Assignment.id == Project.assignment_id
        ).filter(
            Assignment.course_id == cid,
            Project.mode == "academic",
            Project.status.in_(["active", "assessment"]),
        ):
            count += evaluate_project(p)
    return {"detected": count}


@api.route("/projects/<int:pid>/help-requests", methods=["GET", "POST"])
@command()
def help_requests(pid):
    p = project(pid, mutable=request.method == "POST")
    if request.method == "GET":
        return paginate(
            HelpRequest.query.filter_by(project_id=pid).order_by(HelpRequest.id.desc())
        )
    need(enrollment(get(Assignment, p.assignment_id).course_id).role == "student" and membership(pid), "FORBIDDEN", "Chỉ sinh viên trong nhóm được yêu cầu trợ giúp", 403)
    b = json_body()
    tid = b.get("task_id")
    if tid:
        need(task(tid).project_id == pid)
    scope = b.get("scope")
    need(scope in ("group", "task"), message="Cần chọn phạm vi trợ giúp")
    need(
        (scope == "group" and tid is None)
        or (scope == "task" and type(tid) is int and tid > 0),
        message="Cần chọn công việc khi trợ giúp theo công việc",
    )
    from ..academic.collaboration import mentor_ids

    teachers = mentor_ids(pid)
    need(
        teachers,
        "MENTOR_REQUIRED",
        "Cần giảng viên chấp nhận lời mời tham gia nhóm trước",
        409,
    )
    h = HelpRequest(
        project_id=pid,
        task_id=tid,
        requested_by=current_user().id,
        assigned_to=teachers[0],
        subject=textval(b, "subject"),
        content=textval(b, "content"),
    )
    db.session.add(h)
    audit("help.requested", h, pid=pid)
    notify(
        "help.requested",
        h,
        [h.assigned_to] if h.assigned_to else [],
        f"/projects/{pid}?tab=help",
    )
    return dto(h), 201


@api.post("/help-requests/<int:hid>/respond")
@command()
def help_respond(hid):
    h = get(HelpRequest, hid, lock=True)
    project(h.project_id, staff=True, mutable=True)
    need(enrollment(get(Assignment, get(Project, h.project_id).assignment_id).course_id).role == "instructor", "FORBIDDEN", "Chỉ giảng viên được phản hồi yêu cầu hỗ trợ", 403)
    from ..academic.collaboration import require_mentor

    require_mentor(h.project_id)
    version(h)
    state(h, ["submitted", "under_review"])
    b = json_body()
    h.response = textval(b, "response")
    h.assigned_to = current_user().id
    h.status = "resolved" if b.get("resolve") else "under_review"
    h.resolved_at = now() if h.status == "resolved" else None
    audit("help.responded", h, pid=h.project_id, reason=h.response)
    notify("help.responded", h, [h.requested_by], f"/projects/{h.project_id}?tab=help")
    return dto(h)
