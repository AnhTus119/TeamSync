from urllib.parse import urlsplit
from flask import request
from ..academic import api
from ..academic.core import *
from ..models import WorkspaceMember, ProjectMember, Comment, PRIORITIES
from ..common.storage import save_upload, download


def policy_dto(p):
    return {
        **dto(p),
        "criteria": [
            {**dto(c), "levels": rows(CriterionLevel, criterion_id=c.id)}
            for c in Criterion.query.filter_by(policy_id=p.id).order_by(Criterion.id)
        ],
    }


def project_dto(p):
    a = get(Assignment, p.assignment_id)
    e = enrollment(a.course_id)
    m = membership(p.id)
    return {
        **dto(p),
        "my_role": e.role if e.role in STAFF else m.role,
        "progress": {"total": Task.query.filter_by(project_id=p.id).count(), "done": Task.query.filter_by(project_id=p.id,status='done').count()},
        "can_support": bool(
            e.role == "instructor"
            and GroupInvitation.query.filter_by(
                project_id=p.id,
                user_id=current_user().id,
                kind="mentor",
                status="accepted",
            ).first()
            and HelpRequest.query.filter_by(project_id=p.id)
            .filter(HelpRequest.status.in_(["submitted", "under_review"]))
            .first()
        ),
        "members": [
            {
                **dto(x),
                "user": {**user_brief(x.user_id), "email": get(User, x.user_id).email},
            }
            for x in AssignmentMembership.query.filter_by(project_id=p.id)
        ],
        "assignment": dto(a),
        "criteria": [
            dto(c) for c in Criterion.query.filter_by(policy_id=a.published_policy_id)
        ],
    }


def assignment_dto(a):
    return {
        **dto(a),
        "my_role": enrollment(a.course_id).role,
        "policies": [
            policy_dto(p)
            for p in AssessmentPolicy.query.filter_by(assignment_id=a.id).order_by(
                AssessmentPolicy.revision
            )
        ],
    }


@api.route("/courses/<int:cid>/assignments", methods=["GET", "POST"])
@command()
def assignments(cid):
    course(cid, staff=request.method == "POST")
    if request.method == "GET":
        return paginate(
            Assignment.query.filter_by(course_id=cid).filter(True if enrollment(cid).role in STAFF else Assignment.is_hidden.is_(False)).order_by(Assignment.id), dto
        )
    need(enrollment(cid).role == "instructor", "FORBIDDEN", "Chỉ giảng viên được tạo đề bài; coordinator chỉ điều phối lớp và nhân sự", 403)
    b = json_body()
    need(not Assignment.query.filter_by(course_id=cid).first(), "ONE_ASSIGNMENT", "Mỗi lớp chỉ có một bài tập nhóm", 409)
    a = Assignment(
        course_id=cid,
        is_hidden=True,
        title=textval(b, "title"),
        brief=textval(b, "brief"),
        due_at=timestamp(b.get("due_at")),
        opens_at=timestamp(b.get("opens_at"), True),
        group_min=integer(b.get("group_min", 1), 1, 50),
        group_max=integer(b.get("group_max", 5), 1, 50),
    )
    from ..collab.organization import configure_formation
    a.group_mode = b.get('group_mode','self')
    if 'group_mode' not in b and 'formation_due_at' not in b:
        a.formation_due_at = min(a.due_at, now()+timedelta(days=7))
    configure_formation(a, b)
    need(a.group_min <= a.group_max)
    need(a.opens_at is None or a.opens_at < a.due_at)
    db.session.add(a)
    audit("assignment.created", a, cid=cid)
    from ..collab.organization import materialize_teacher_groups
    materialize_teacher_groups(a)
    return dto(a), 201


@api.route("/assignments/<int:aid>", methods=["GET", "PATCH"])
@command()
def assignment_detail(aid):
    a = assignment(aid, staff=request.method == "PATCH")
    if request.method == "PATCH":
        need(enrollment(a.course_id).role == "instructor", "FORBIDDEN", "Chỉ giảng viên được sửa đề bài", 403)
        state(a, ["draft","published","active"])
        version(a)
        b = json_body()
        for k in ("title", "brief"):
            if k in b:
                setattr(a, k, textval(b, k))
        if "due_at" in b:
            a.due_at = timestamp(b["due_at"])
        if "opens_at" in b:
            a.opens_at = timestamp(b["opens_at"], True)
        for k in ("group_min", "group_max"):
            if k in b:
                setattr(a, k, integer(b[k], 1, 50))
        need(a.group_min <= a.group_max)
        if "due_at" in b:
            need(not Task.query.join(Project,Project.id==Task.project_id).filter(Project.assignment_id==aid,Task.due_at>a.due_at).first(),message="Hạn nộp bài mới sớm hơn hạn công việc hiện có")
        need(a.opens_at is None or a.opens_at<a.due_at,message="Ngày mở phải trước hạn nộp")
        from ..collab.organization import configure_formation
        configure_formation(a,b)
        need(not a.formation_due_at or a.formation_due_at<=a.due_at,message="Hạn lập nhóm không được vượt hạn nộp bài")
        for p in Project.query.filter_by(assignment_id=aid):
            need(AssignmentMembership.query.filter_by(project_id=p.id,status="active").count()<=a.group_max,message="Số thành viên nhóm hiện tại vượt giới hạn mới")
        audit("assignment.updated", a, cid=a.course_id)
        from ..collab.organization import materialize_teacher_groups
        materialize_teacher_groups(a)
    return assignment_dto(a)


@api.route("/assignments/<int:aid>/policies", methods=["GET", "POST"])
@command()
def policies(aid):
    a = assignment(aid, staff=request.method == "POST")
    if request.method == "POST":
        need(enrollment(a.course_id).role == "instructor", "FORBIDDEN", "Chỉ giảng viên được tạo bộ tiêu chí", 403)
    if request.method == "GET":
        return paginate(
            AssessmentPolicy.query.filter_by(assignment_id=aid).order_by(
                AssessmentPolicy.revision
            ),
            policy_dto,
        )
    need(
        a.status == "draft",
        "POLICY_LOCKED",
        "Chính sách đã khóa; liên hệ người phụ trách",
        409,
    )
    b = json_body()
    revision = (
        db.session.query(db.func.max(AssessmentPolicy.revision))
        .filter_by(assignment_id=aid)
        .scalar()
        or 0
    ) + 1
    p = AssessmentPolicy(
        assignment_id=aid,
        revision=revision,
        appeal_window_hours=integer(b.get("appeal_window_hours", 72), 1, 720),
        scale_max=10,
    )
    db.session.add(p)
    db.session.flush()
    save_criteria(p, b.get("criteria", []))
    audit("policy.created", p, cid=a.course_id)
    return policy_dto(p), 201


def save_criteria(p, items):
    need(isinstance(items, list) and 1 <= len(items) <= 30, message="Cần 1–30 tiêu chí")
    for c in Criterion.query.filter_by(policy_id=p.id).all():
        CriterionLevel.query.filter_by(criterion_id=c.id).delete()
        db.session.delete(c)
    db.session.flush()
    codes = set()
    for item in items:
        need(isinstance(item, dict), message="Tiêu chí phải là một đối tượng")
        code = textval(item, "code")
        need(code not in codes)
        codes.add(code)
        c = Criterion(
            policy_id=p.id,
            code=code,
            title=textval(item, "title"),
            description=item.get("description", ""),
            weight=decimal(item.get("weight"), 0.01),
            max_score=10,
            evidence_requirement=item.get(
                "evidence_requirement", "Minh chứng hoặc kiểm tra trực tiếp"
            ),
        )
        db.session.add(c)
        db.session.flush()
        levels = item.get("levels", [])
        need(
            isinstance(levels, list) and len(levels) <= 4,
            message="Cần tối đa bốn mức đánh giá",
        )
        for i, l in enumerate(levels):
            need(isinstance(l, dict), message="Mức đánh giá phải là một đối tượng")
            db.session.add(
                CriterionLevel(
                    criterion_id=c.id,
                    label=textval(l, "label"),
                    score=decimal(l.get("score"), 0, 10),
                    description=textval(l, "description"),
                    ordinal=i,
                )
            )


@api.patch("/policies/<int:pid>")
@command()
def policy_update(pid):
    p = get(AssessmentPolicy, pid)
    a = assignment(p.assignment_id, staff=True)
    need(enrollment(a.course_id).role == "instructor", "FORBIDDEN", "Chỉ giảng viên được sửa bộ tiêu chí", 403)
    need(
        p.status == "draft" and a.status == "draft",
        "POLICY_LOCKED",
        "Chính sách đã công bố không sửa trực tiếp",
        409,
    )
    version(p)
    b = json_body()
    if "criteria" in b:
        save_criteria(p, b["criteria"])
    if "appeal_window_hours" in b:
        p.appeal_window_hours = integer(b["appeal_window_hours"], 1, 720)
    audit("policy.updated", p, cid=a.course_id)
    return policy_dto(p)


@api.post("/policies/<int:pid>/publish")
@command(idempotent=True)
def policy_publish(pid):
    p = get(AssessmentPolicy, pid, lock=True)
    a = assignment(p.assignment_id, staff=True)
    need(enrollment(a.course_id).role == "instructor", "FORBIDDEN", "Chỉ giảng viên được công bố bộ tiêu chí", 403)
    state(p, ["draft"])
    need(a.status == "draft", "POLICY_LOCKED", "Chính sách đã khóa", 409)
    version(p)
    cs = Criterion.query.filter_by(policy_id=pid).all()
    need(
        cs and sum(c.weight for c in cs) == 100,
        "WEIGHTS_INVALID",
        "Tổng trọng số phải bằng 100",
        409,
    )
    for c in cs:
        levels = CriterionLevel.query.filter_by(criterion_id=c.id).all()
        need(
            c.description
            and c.evidence_requirement
            and len(levels) == 4
            and len({l.description.strip() for l in levels}) == 4,
            "RUBRIC_INCOMPLETE",
            "Mỗi tiêu chí cần mô tả, minh chứng và bốn mức đánh giá có nội dung riêng",
            409,
        )
    for old in AssessmentPolicy.query.filter_by(assignment_id=a.id, status="published"):
        old.status = "superseded"
    p.status = "published"
    p.published_at = now()
    a.published_policy_id = p.id
    a.version += 1
    audit("policy.published", p, cid=a.course_id)
    return policy_dto(p)


@api.post("/assignments/<int:aid>/publish")
@api.post("/assignments/<int:aid>/activate")
@command(idempotent=True)
def assignment_command(aid):
    a = assignment(aid, staff=True)
    need(enrollment(a.course_id).role == "instructor", "FORBIDDEN", "Chỉ giảng viên được thay đổi trạng thái đề bài", 403)
    version(a)
    need(
        CourseEnrollment.query.filter_by(
            course_id=a.course_id, status="active", role="instructor"
        ).first(),
        "INSTRUCTOR_REQUIRED",
        "Cần phân công giảng viên",
        409,
    )
    if request.path.endswith("/publish"):
        state(a, ["draft"])
        need(
            a.brief and a.published_policy_id and a.due_at > now(),
            "POLICY_REQUIRED",
            "Cần nội dung, hạn hợp lệ và bộ tiêu chí đã công bố",
            409,
        )
        a.status = "published"
        a.is_hidden = False
    else:
        state(a, ["published"])
        a.status = "active"
    audit("assignment." + a.status, a, cid=a.course_id)
    return dto(a)


def add_group_member(p, uid, role):
    a = get(Assignment, p.assignment_id)
    if current_user() and enrollment(a.course_id).role == "student":
        need(not AssignmentMembership.query.filter_by(assignment_id=a.id,user_id=uid).filter(AssignmentMembership.status != "active").first(), "REJOIN_TEACHER", "Cần giảng viên xếp lại nhóm sau khi rời", 409)
    e = enrollment(a.course_id, uid)
    need(
        e and e.role == "student",
        "INVALID_PARTICIPANT",
        "Sinh viên phải đang học trong lớp",
    )
    need(
        not AssignmentMembership.query.filter_by(
            assignment_id=a.id, user_id=uid, status="active"
        ).first(),
        "MEMBERSHIP_CONFLICT",
        "Sinh viên đã có nhóm trong đề bài",
        409,
    )
    need(
        AssignmentMembership.query.filter_by(project_id=p.id, status="active").count()
        < a.group_max,
        "GROUP_SIZE_INVALID",
        "Nhóm đã đủ số thành viên",
        409,
    )
    need(role in ("member", "leader"))
    if role == "leader":
        need(
            not AssignmentMembership.query.filter_by(
                project_id=p.id, status="active", role="leader"
            ).first(),
            "MEMBERSHIP_CONFLICT",
            "Nhóm đã có trưởng nhóm",
            409,
        )
    db.session.add(
        AssignmentMembership(
            assignment_id=a.id, project_id=p.id, user_id=uid, role=role
        )
    )
    old = ProjectMember.query.filter_by(project_id=p.id, user_id=uid).first()
    if not old:
        db.session.add(
            ProjectMember(
                project_id=p.id,
                user_id=uid,
                project_role="manager" if role == "leader" else "member",
            )
        )
    w = get(CourseOffering, a.course_id).workspace_id
    if not WorkspaceMember.query.filter_by(workspace_id=w, user_id=uid).first():
        db.session.add(WorkspaceMember(workspace_id=w, user_id=uid, role="member"))


@api.route("/assignments/<int:aid>/projects", methods=["GET", "POST"])
@command()
def groups(aid):
    a = assignment(aid)
    if request.method == "GET":
        q = Project.query.filter_by(assignment_id=aid)
        if enrollment(a.course_id).role not in STAFF:
            q = q.join(
                AssignmentMembership, AssignmentMembership.project_id == Project.id
            ).filter(
                AssignmentMembership.user_id == current_user().id,
                AssignmentMembership.status == "active",
            )
        return paginate(q.order_by(Project.id), project_dto)
    need(enrollment(a.course_id).role == "student", "FORBIDDEN", "Chỉ sinh viên được tạo nhóm dự án", 403)
    from ..collab.organization import require_self_formation
    require_self_formation(a)
    need(
        a.status in ("draft", "published", "active"),
        "FINALIZED_LOCKED",
        "Đề bài không còn nhận nhóm",
        409,
    )
    b = json_body()
    p = Project(
        workspace_id=get(CourseOffering, a.course_id).workspace_id,
        name=textval(b, "name"),
        description=b.get("description", ""),
        created_by=current_user().id,
        created_at=now().replace(tzinfo=None),
        assignment_id=aid,
        mode="academic",
        status="draft",
    )
    db.session.add(p)
    db.session.flush()
    if enrollment(a.course_id).role == "student":
        need(
            not b.get("members"),
            "INVITATION_REQUIRED",
            "Thành viên cần chấp nhận lời mời",
        )
        add_group_member(p, current_user().id, "leader")
        db.session.flush()
    else:
        for m in b.get("members", []):
            add_group_member(p, integer(m.get("user_id")), m.get("role", "member"))
            db.session.flush()
    audit("project.created", p, cid=a.course_id, pid=p.id)
    return project_dto(p), 201


@api.route("/projects/<int:pid>", methods=["GET", "PATCH"])
@command()
def project_detail(pid):
    p = project(
        pid, manage=request.method == "PATCH", mutable=request.method == "PATCH"
    )
    if request.method == "PATCH":
        version(p)
        b = json_body()
        need(
            "status" not in b,
            "INVALID_TRANSITION",
            "Dùng thao tác chuyển trạng thái",
            409,
        )
        for key in ("name", "description"):
            if key in b:
                setattr(p, key, textval(b, key))
        audit("project.updated", p, pid=pid)
    return project_dto(p)


@api.post("/projects/<int:pid>/members")
@command()
def group_members(pid):
    p = project(pid, manage=True, mutable=True)
    version(p)
    need(
        p.status == "draft",
        "CHANGE_REQUEST_REQUIRED",
        "Cần yêu cầu thay đổi thành viên khi nhóm đã hoạt động",
        409,
    )
    b = json_body()
    add_group_member(p, integer(b.get("user_id")), b.get("role", "member"))
    audit("project.member_added", p, pid=pid)
    return project_dto(p)


@api.post("/projects/<int:pid>/activate")
@command()
def group_activate(pid):
    p = project(pid, manage=True, mutable=True)
    version(p)
    state(p, ["draft"])
    a = get(Assignment, p.assignment_id)
    need(a.status == "active", "INVALID_TRANSITION", "Đề bài chưa kích hoạt", 409)
    n = AssignmentMembership.query.filter_by(project_id=pid, status="active").count()
    need(
        a.group_min <= n <= a.group_max
        and AssignmentMembership.query.filter_by(
            project_id=pid, status="active", role="leader"
        ).count()
        == 1,
        "GROUP_SIZE_INVALID",
        "Cần đủ thành viên và một trưởng nhóm",
        409,
    )
    p.status = "active"
    audit("project.activated", p, pid=pid)
    return project_dto(p)


@api.post("/projects/<int:pid>/archive")
@command()
def group_archive(pid):
    p = project(pid, manage=True)
    version(p)
    state(p, ["finalized", "draft"])
    need(
        p.status == "finalized"
        or AssignmentMembership.query.filter_by(project_id=pid, status="active").count()
        == 0,
        "ACTIVE_MEMBERS_EXIST",
        "Chuyển hoặc rút thành viên trước khi lưu trữ nhóm nháp",
        409,
    )
    p.status = "archived"
    audit("project.archived", p, pid=pid)
    return dto(p)


def set_task_relations(t, b):
    p = get(Project, t.project_id)
    a = get(Assignment, p.assignment_id)
    if "participants" in b:
        members = b["participants"]
        need(
            isinstance(members, list)
            and members
            and sum(m.get("role") == "responsible" for m in members) == 1,
            "INVALID_PARTICIPANT",
            "Cần đúng một người chịu trách nhiệm",
        )
        ids = []
        for m in members:
            uid = integer(m.get("user_id"))
            need(
                membership(p.id, uid) and enrollment(a.course_id, uid),
                "INVALID_PARTICIPANT",
                "Người làm phải đang thuộc nhóm",
            )
            need(m.get("role") in ("responsible", "collaborator"))
            ids.append(uid)
        need(
            len(ids) == len(set(ids)), "INVALID_PARTICIPANT", "Người tham gia bị trùng"
        )
        TaskParticipant.query.filter_by(task_id=t.id).delete()
        db.session.flush()
        for m in members:
            db.session.add(
                TaskParticipant(task_id=t.id, user_id=m["user_id"], role=m["role"])
            )
            if m["role"] == "responsible":
                t.primary_assignee_id = t.assignee_id = m["user_id"]
    if "criterion_ids" in b:
        ids = b["criterion_ids"]
        need(isinstance(ids, list) and ids, "EVIDENCE_REQUIRED", "Cần chọn tiêu chí")
        for cid in set(ids):
            need(
                get(Criterion, integer(cid)).policy_id == a.published_policy_id,
                "INVALID_EVIDENCE_SCOPE",
                "Tiêu chí khác chính sách",
            )
        TaskCriterion.query.filter_by(task_id=t.id).delete()
        for cid in set(ids):
            db.session.add(TaskCriterion(task_id=t.id, criterion_id=cid))
    if "milestone_id" in b:
        mid = b["milestone_id"]
        if mid:
            need(get(Milestone, mid).project_id == t.project_id)
        t.milestone_id = mid


@api.route("/projects/<int:pid>/tasks", methods=["GET", "POST"])
@command()
def tasks(pid):
    p = project(pid, mutable=request.method == "POST")
    if request.method == "POST":
        from ..collab.services import team
        team(pid)
    if request.method == "GET":
        q = Task.query.filter_by(project_id=pid)
        if request.args.get("status"):
            q = q.filter_by(status=request.args["status"])
        return paginate(
            q.order_by(Task.due_at, Task.id), task_summary, prefetch=prefetch_tasks
        )
    state(p, ["active"])
    b = json_body()
    need(
        b.get("participants"),
        "INVALID_PARTICIPANT",
        "Cần chọn người làm",
    )
    t = Task(
        project_id=pid,
        title=textval(b, "title"),
        description=textval(b, "description"),
        due_at=timestamp(b.get("due_at")),
        points=integer(b.get("points", 1), 1, 5),
        created_by=current_user().id,
        created_at=now().replace(tzinfo=None),
        updated_at=now().replace(tzinfo=None),
        status="todo",
        priority=b.get("priority", "medium"),
    )
    need(t.points in (1, 2, 3, 5))
    need(t.priority in PRIORITIES, "VALIDATION_ERROR", "Ưu tiên không hợp lệ")
    need(t.due_at <= get(Assignment,p.assignment_id).due_at, message="Hạn công việc không được vượt hạn đề bài")
    t.original_due_at = t.due_at
    db.session.add(t)
    db.session.flush()
    set_task_relations(t, b)
    audit("task.created", t, pid=pid)
    db.session.flush()
    return task_dto(t), 201


@api.route("/tasks/<int:tid>", methods=["GET", "PATCH"])
@command()
def task_detail(tid):
    t = task(tid, manage=request.method == "PATCH", mutable=request.method == "PATCH")
    if request.method == "PATCH":
        b = json_body()
        version(t, b)
        need(
            "status" not in b,
            "INVALID_TRANSITION",
            "Dùng thao tác chuyển trạng thái",
            409,
        )
        locked_fields = (
            "participants",
            "points",
            "due_at",
            "criterion_ids",
            "milestone_id",
        )
        need(
            not any(k in b for k in locked_fields) or t.status == "todo",
            "CHANGE_REQUEST_REQUIRED",
            "Thay đổi sau khi bắt đầu cần được duyệt",
            409,
        )
        need(
            "due_at" not in b,
            "CHANGE_REQUEST_REQUIRED",
            "Sử dụng yêu cầu gia hạn để trưởng nhóm duyệt",
            409,
        )
        for k in ("title", "description"):
            if k in b:
                setattr(t, k, textval(b, k))
        if "priority" in b:
            need(b["priority"] in PRIORITIES, "VALIDATION_ERROR", "Ưu tiên không hợp lệ")
            t.priority = b["priority"]
        if "points" in b:
            need(b["points"] in (1, 2, 3, 5))
            t.points = b["points"]
        set_task_relations(t, b)
        audit("task.updated", t, pid=t.project_id)
    return task_dto(t)


@api.post("/tasks/<int:tid>/start")
@command()
def task_start(tid):
    t = task(tid, mutable=True)
    participant(t)
    version(t)
    state(t, ["todo"])
    t.status = "in_progress"
    t.last_progress_at = now()
    audit("task.started", t, pid=t.project_id)
    return task_dto(t)


@api.route("/tasks/<int:tid>/dependencies", methods=["POST"])
@api.delete("/tasks/<int:tid>/dependencies/<int:dependency_id>")
@command()
def task_dependency(tid, dependency_id=None):
    need(
        False,
        "FEATURE_REMOVED",
        "Công việc được thực hiện độc lập; hệ thống đã bỏ chức năng phụ thuộc",
        410,
    )


@api.post("/tasks/<int:tid>/assets")
@command()
def asset_upload(tid):
    t = task(tid, mutable=True)
    participant(t)
    state(t, ["in_progress"])
    total = (
        db.session.query(db.func.coalesce(db.func.sum(EvidenceAsset.size_bytes), 0))
        .join(Task, Task.id == EvidenceAsset.task_id)
        .filter(Task.project_id == t.project_id)
        .scalar()
    )
    total += (
        db.session.query(db.func.coalesce(db.func.sum(AppealEvidence.size_bytes), 0))
        .join(Appeal, Appeal.id == AppealEvidence.appeal_id)
        .join(AssessmentRecord, AssessmentRecord.id == Appeal.assessment_record_id)
        .filter(AssessmentRecord.project_id == t.project_id)
        .scalar()
    )
    if request.files.get("file"):
        need(
            total < current_limit("MAX_PROJECT_BYTES"),
            "QUOTA_EXCEEDED",
            "Nhóm đã dùng hết dung lượng",
            413,
        )
        info = save_upload(request.files["file"])
        if total + info["size_bytes"] > current_limit("MAX_PROJECT_BYTES"):
            from ..common.storage import root

            (root() / info["storage_key"]).unlink(missing_ok=True)
            need(False, "QUOTA_EXCEEDED", "Vượt dung lượng nhóm", 413)
        x = EvidenceAsset(
            task_id=tid,
            uploaded_by=current_user().id,
            kind="file",
            integrity_status="fixed_file",
            **info,
        )
    else:
        b = json_body()
        url = textval(b, "url")
        try:
            u = urlsplit(url)
            valid = (
                u.scheme in ("http", "https")
                and u.hostname
                and not u.username
                and not u.password
            )
        except ValueError:
            valid = False
        need(
            valid, message="Liên kết phải là http/https, không chứa thông tin đăng nhập"
        )
        x = EvidenceAsset(
            task_id=tid,
            uploaded_by=current_user().id,
            kind="link",
            url=url,
            integrity_status="external_mutable",
            size_bytes=0,
        )
    db.session.add(x)
    audit("asset.created", x, pid=t.project_id)
    return asset_dto(x), 201


def current_limit(name):
    from flask import current_app

    return current_app.config[name]


@api.get("/assets/<int:aid>/download")
def asset_download(aid):
    need(current_user() is not None, "UNAUTHORIZED", "Bạn cần đăng nhập", 401)
    x = get(EvidenceAsset, aid)
    personal_evidence_scope(get(Task, x.task_id), asset=x)
    need(
        x.kind == "file" and x.integrity_status != "missing",
        "NOT_FOUND",
        "File không khả dụng",
        404,
    )
    return download(x.storage_key, x.original_filename, x.sha256)


@api.post("/tasks/<int:tid>/evidence-revisions")
@command()
def evidence_revision_create(tid):
    t = task(tid, mutable=True)
    participant(t)
    version(t)
    state(t, ["in_progress"])
    r = create_evidence_revision(t, json_body())
    return revision_dto(r), 201


def create_evidence_revision(t, b):
    """Capture the submitted content within the caller's transaction."""
    tid = t.id
    ids = b.get("asset_ids")
    need(
        isinstance(ids, list) and ids and all(type(x) is int and x > 0 for x in ids),
        "EVIDENCE_REQUIRED",
        "Cần ít nhất một file hoặc liên kết",
        409,
    )
    assets = [get(EvidenceAsset, integer(x)) for x in set(ids)]
    need(
        all(x.task_id == tid and x.integrity_status != "missing" for x in assets),
        "INVALID_EVIDENCE_SCOPE",
        "Minh chứng không thuộc nhiệm vụ",
    )
    need(
        sum(x.size_bytes for x in assets) <= current_limit("MAX_REVISION_BYTES"),
        "QUOTA_EXCEEDED",
        "Phiên bản vượt 50 MiB",
        413,
    )
    n = (
        db.session.query(db.func.max(EvidenceRevision.revision_no))
        .filter_by(task_id=tid)
        .scalar()
        or 0
    ) + 1
    r = EvidenceRevision(
        task_id=tid,
        revision_no=n,
        description=textval(b, "description"),
        created_by=current_user().id,
    )
    db.session.add(r)
    db.session.flush()
    for x in assets:
        db.session.add(EvidenceRevisionAsset(revision_id=r.id, asset_id=x.id))
    t.last_progress_at = now()
    audit("evidence.revision_created", r, pid=t.project_id)
    db.session.flush()
    return r


@api.get("/evidence-revisions/<int:rid>")
@command()
def revision_detail(rid):
    r = get(EvidenceRevision, rid)
    personal_evidence_scope(get(Task, r.task_id), revision=r)
    return revision_dto(r)


@api.post("/tasks/<int:tid>/submissions")
@command(idempotent=True)
def task_submit(tid):
    t = task(tid, mutable=True)
    participant(t)
    version(t)
    state(t, ["in_progress"])
    b = json_body()
    r = (
        get(EvidenceRevision, integer(b["revision_id"]))
        if "revision_id" in b
        else create_evidence_revision(t, b)
    )
    need(r.task_id == tid, "INVALID_EVIDENCE_SCOPE", "Phiên bản khác nhiệm vụ")
    need(
        EvidenceRevisionAsset.query.filter_by(revision_id=r.id).first(),
        "EVIDENCE_REQUIRED",
        "Cần file hoặc liên kết sản phẩm",
        409,
    )
    n = TaskSubmission.query.filter_by(task_id=tid).count() + 1
    s = TaskSubmission(
        task_id=tid,
        revision_id=r.id,
        attempt_no=n,
        submitted_by=current_user().id,
        participant_ids=sorted(
            x.user_id for x in TaskParticipant.query.filter_by(task_id=tid)
        ),
        received_at=now(),
        submitted_due_at=t.due_at,
    )
    db.session.add(s)
    db.session.flush()
    from ..collab.services import bind_submission
    bind_submission(t,s,b.get("branch_id"))
    t.latest_submission_id = s.id
    t.status = "review"
    t.last_progress_at = now()
    audit("task.submitted", s, pid=t.project_id)
    p = get(Project, t.project_id)
    members = [
        m.user_id
        for m in AssignmentMembership.query.filter_by(project_id=p.id, status="active")
    ]
    notify("submission.pending", s, members, f"/tasks/{tid}")
    return {
        **dto(s),
        "late": s.received_at > s.submitted_due_at,
        "task_version": t.version,
    }, 201


@api.post("/submissions/<int:sid>/review")
@command(idempotent=True)
def submission_review(sid):
    s = get(TaskSubmission, sid, lock=True)
    t = task(s.task_id, mutable=True)
    version(t)
    state(t, ["review"])
    state(s, ["pending"])
    need(
        t.latest_submission_id == sid,
        "VERSION_CONFLICT",
        "Bản nộp đang xem đã thay đổi",
        409,
    )
    m = membership(t.project_id)
    need(m and not is_staff(get(Project,t.project_id)) and (m.role == "leader" or s.submitted_by != current_user().id),
         "FORBIDDEN", "Thành viên không được tự duyệt bài mình nộp", 403)
    b = json_body()
    action = b.get("action")
    need(action in ("accept", "return"))
    raw_reason = b.get("reason") or ""
    need(isinstance(raw_reason, str))
    reason = raw_reason.strip()
    need(
        action != "return" or reason,
        "REVIEW_REASON_REQUIRED",
        "Yêu cầu sửa cần nêu lý do",
    )
    if action == "return":
        repair_due = timestamp(b.get("repair_due_at"))
        need(now() < repair_due <= get(Assignment, get(Project,t.project_id).assignment_id).due_at, message="Hạn sửa phải sau hiện tại và không vượt hạn bài tập")
        t.due_at = repair_due
    s.status = "accepted" if action == "accept" else "returned"
    s.reviewed_by = current_user().id
    s.reviewed_at = now()
    s.review_reason = reason
    t.status = "done" if action == "accept" else "in_progress"
    t.completed_at = now().replace(tzinfo=None) if action == "accept" else None
    audit("submission." + s.status, s, pid=t.project_id, reason=reason)
    from ..models.teamwork import BranchMergeRequest, TaskBranch
    binding = BranchMergeRequest.query.filter_by(submission_id=s.id).first()
    if binding:
        branch = get(TaskBranch,binding.branch_id)
        branch.status = "merged" if action == "accept" else "open"
    notify("submission.reviewed", s, s.participant_ids, f"/tasks/{t.id}")
    return {**dto(s), "task_version": t.version}


@api.post("/tasks/<int:tid>/progress-checkins")
@command()
def checkin(tid):
    t = task(tid, mutable=True)
    participant(t)
    version(t)
    state(t, ["in_progress"])
    b = json_body()
    c = ProgressCheckin(
        task_id=tid,
        user_id=current_user().id,
        content=textval(b, "content", 10),
        evidence_refs=evidence_refs(b.get("evidence_refs", []), t=t, required=False),
    )
    db.session.add(c)
    t.last_progress_at = now()
    audit("progress.self_reported", c, pid=t.project_id)
    return dto(c), 201


@api.route("/projects/<int:pid>/change-requests", methods=["GET", "POST"])
@command()
def changes(pid):
    p = project(pid, mutable=request.method == "POST")
    if request.method == "GET":
        return paginate(
            ChangeRequest.query.filter_by(project_id=pid).order_by(
                ChangeRequest.id.desc()
            )
        )
    need(enrollment(get(Assignment, p.assignment_id).course_id).role == "student" and membership(pid) is not None, "FORBIDDEN", "Chỉ sinh viên trong nhóm mới được gửi đề nghị thay đổi", 403)
    b = json_body()
    need(b.get("kind") != "deadline", "EXTENSION_API_REQUIRED", "Dùng yêu cầu gia hạn để trưởng nhóm duyệt và ghi nhận chỉ số cam kết",409)
    kind = b.get("kind")
    need(kind in ("deadline", "assignee", "points", "membership", "reopen"))
    t = task(b["task_id"]) if b.get("task_id") else None
    need((kind == "membership") or t is not None)
    need(t is None or t.project_id == pid)
    proposed = b.get("proposed")
    need(isinstance(proposed, dict) and proposed)
    c = ChangeRequest(
        project_id=pid,
        task_id=t.id if t else None,
        kind=kind,
        before_json=(
            dto(t) if t else {"members": rows(AssignmentMembership, project_id=pid)}
        ),
        proposed_json=proposed,
        reason=textval(b, "reason"),
        requested_by=current_user().id,
    )
    db.session.add(c)
    audit("change.requested", c, pid=pid)
    return dto(c), 201


@api.get("/change-requests/<int:cid>")
@command()
def change_detail(cid):
    c = get(ChangeRequest, cid)
    project(c.project_id)
    return dto(c)


@api.post("/change-requests/<int:cid>/decide")
@command(idempotent=True)
def change_decide(cid):
    c = get(ChangeRequest, cid, lock=True)
    p = project(c.project_id, manage=True, mutable=True)
    version(c)
    state(c, ["pending"])
    b = json_body()
    action = b.get("action")
    need(action in ("approve", "reject"))
    reason = textval(b, "reason")
    if action == "approve":
        prop = c.proposed_json
        t = task(c.task_id, mutable=True) if c.task_id else None
        if t:
            t.version += 1
        if c.kind == "deadline":
            t.due_at = timestamp(prop.get("due_at"))
            need(
                t.due_at <= get(Assignment, p.assignment_id).due_at,
                message="Hạn công việc không được vượt hạn đề bài",
            )
        elif c.kind == "assignee":
            set_task_relations(t, {"participants": prop.get("participants")})
        elif c.kind == "points":
            need(prop.get("points") in (1, 2, 3, 5))
            t.points = prop["points"]
        elif c.kind == "reopen":
            state(t, ["done"])
            t.status = "in_progress"
            t.completed_at = None
        elif c.kind == "membership":
            from ..collab.organization import require_self_formation
            if enrollment(get(Assignment,p.assignment_id).course_id).role == "student":
                require_self_formation(get(Assignment,p.assignment_id))
            uid = integer(prop.get("user_id"))
            operation = prop.get("operation")
            need(operation in ("leave", "add", "transfer", "change_role"))
            if operation in ("leave", "transfer"):
                m = membership(p.id, uid)
                need(m is not None)
                need(
                    m.role != "leader"
                    or AssignmentMembership.query.filter_by(
                        project_id=p.id, status="active"
                    ).count()
                    == 1,
                    "LEADER_REPLACEMENT_REQUIRED",
                    "Cần chỉ định trưởng nhóm thay thế trước khi rời nhóm",
                    409,
                )
                m.status = "left"
                m.left_at = now()
                db.session.flush()
            if operation == "change_role":
                member = membership(p.id, uid)
                need(member is not None)
                role = prop.get("role")
                need(role in ("leader", "member"))
                if role == "leader":
                    for old in AssignmentMembership.query.filter_by(
                        project_id=p.id, status="active", role="leader"
                    ):
                        old.role = "member"
                    member.role = "leader"
                else:
                    need(
                        member.role != "leader",
                        "LEADER_REPLACEMENT_REQUIRED",
                        "Chọn trưởng nhóm mới trước khi hạ vai trò",
                        409,
                    )
                    member.role = "member"
            if operation == "add":
                add_group_member(p, uid, prop.get("role", "member"))
            if operation == "transfer":
                dest = project(
                    integer(prop.get("project_id")), staff=True, mutable=True
                )
                need(dest.assignment_id == p.assignment_id)
                add_group_member(dest, uid, prop.get("role", "member"))
    c.status = "approved" if action == "approve" else "rejected"
    c.decided_by = current_user().id
    c.decided_at = now()
    c.decision_reason = reason
    audit("change." + c.status, c, pid=c.project_id, reason=reason)
    return dto(c)


@api.route("/projects/<int:pid>/milestones", methods=["GET", "POST"])
@command()
def milestones(pid):
    project(pid, manage=request.method == "POST", mutable=request.method == "POST")
    if request.method == "GET":
        return paginate(
            Milestone.query.filter_by(project_id=pid).order_by(Milestone.id),
            lambda m: {
                **dto(m),
                "tasks": [dto(t) for t in Task.query.filter_by(milestone_id=m.id)],
            },
        )
    b = json_body()
    m = Milestone(
        project_id=pid,
        title=textval(b, "title"),
        description=textval(b, "description"),
        due_at=timestamp(b.get("due_at")),
        required=bool(b.get("required", True)),
        created_at=now().replace(tzinfo=None),
    )
    db.session.add(m)
    audit("milestone.created", m, pid=pid)
    return dto(m), 201


@api.route("/milestones/<int:mid>", methods=["GET", "PATCH"])
@command()
def milestone_detail(mid):
    m = get(Milestone, mid)
    project(
        m.project_id,
        manage=request.method == "PATCH",
        mutable=request.method == "PATCH",
    )
    if request.method == "PATCH":
        version(m)
        state(m, ["open"])
        b = json_body()
        m.title = textval(b, "title")
        m.description = b.get("description", "")
        audit("milestone.updated", m, pid=m.project_id)
    return {**dto(m), "tasks": [dto(t) for t in Task.query.filter_by(milestone_id=mid)]}


@api.post("/milestones/<int:mid>/submit")
@api.post("/milestones/<int:mid>/review")
@command()
def milestone_command(mid):
    m = get(Milestone, mid, lock=True)
    review = request.path.endswith("/review")
    p = project(m.project_id, staff=review, manage=not review, mutable=True)
    version(m)
    b = json_body()
    tasks = Task.query.filter_by(milestone_id=mid).all()
    need(
        tasks and all(t.status == "done" for t in tasks),
        "INCOMPLETE_TASKS",
        "Cần hoàn thành các nhiệm vụ của cột mốc",
        409,
    )
    if review:
        state(m, ["open", "pending_review", "changes_requested"])
        need(
            not any(
                TaskParticipant.query.filter_by(
                    task_id=t.id, user_id=current_user().id
                ).first()
                for t in tasks
            ),
            "SELF_APPROVAL_FORBIDDEN",
            "Không tự nghiệm thu",
            403,
        )
        action = b.get("action")
        need(action in ("accept", "request_changes"))
        m.status = "accepted" if action == "accept" else "changes_requested"
        m.review_note = textval(b, "reason")
        m.reviewed_by = current_user().id
        m.reviewed_at = now().replace(tzinfo=None)
    else:
        state(m, ["open", "changes_requested"])
        m.status = "pending_review"
    audit("milestone." + m.status, m, pid=p.id)
    return dto(m)


@api.get("/projects/<int:pid>/audit")
@command()
def project_audit(pid):
    project(pid)
    return paginate(
        AuditEvent.query.filter_by(project_id=pid).order_by(AuditEvent.id.desc()),
        lambda e: dto(e, omit=("before_json", "after_json", "reason")),
    )


@api.route("/tasks/<int:tid>/comments", methods=["GET", "POST"])
@command()
def academic_comments(tid):
    t = task(tid, mutable=request.method == "POST")
    if request.method == "GET":
        return paginate(
            Comment.query.filter_by(task_id=tid).order_by(Comment.id),
            lambda c: c.to_dict(),
        )
    need(enrollment(get(Assignment, get(Project, t.project_id).assignment_id).course_id).role == "student" and membership(t.project_id) is not None, "FORBIDDEN", "Trao đổi trong nhiệm vụ chỉ dành cho thành viên sinh viên", 403)
    c = Comment(
        task_id=tid, user_id=current_user().id, content=textval(json_body(), "content")
    )
    db.session.add(c)
    audit("comment.created", c, pid=t.project_id)
    return dto(c), 201
