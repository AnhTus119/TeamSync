"""Shared academic scope, validation, DTOs, and transactional command wrapper."""

import functools, hashlib, json, uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from flask import request, g, jsonify
from sqlalchemy import text as sqltext
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm.exc import StaleDataError
from ..extensions import db
from ..models import User, Project, Task, Milestone
from ..models.academic import *
from ..common.clock import now, iso
from ..common.responses import fail, json_body
from ..m20_accounts.permissions import current_user

STAFF = ("instructor", "coordinator")


def need(test, code="VALIDATION_ERROR", message="Dữ liệu không hợp lệ", status=400):
    if not test:
        fail(status, code, message)


def textval(body, key, minimum=1, default=None):
    value = body.get(key, default)
    need(
        isinstance(value, str)
        and len(value.strip()) >= minimum
        and len(value) <= 20000,
        message=f"{key}: cần nhập nội dung hợp lệ",
    )
    return value.strip()


def integer(value, low=1, high=2147483647):
    need(
        isinstance(value, int) and not isinstance(value, bool) and low <= value <= high
    )
    return value


def decimal(value, low=0, high=100):
    try:
        v = Decimal(str(value))
    except (InvalidOperation, TypeError):
        need(False)
        return
    need(v.is_finite() and Decimal(str(low)) <= v <= Decimal(str(high)))
    need(v.as_tuple().exponent >= -2, message="Tối đa hai chữ số thập phân")
    return v


def timestamp(value, optional=False):
    if optional and not value:
        return None
    try:
        d = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, TypeError, AttributeError):
        need(False, message="Thời gian phải là ISO 8601 có múi giờ")
        return
    need(d.tzinfo is not None, message="Thời gian phải có múi giờ")
    return d.astimezone(timezone.utc)


def get(cls, ident, lock=False):
    obj = (
        db.session.execute(
            db.select(cls)
            .where(cls.id == ident)
            .with_for_update()
            .execution_options(populate_existing=True)
        ).scalar_one_or_none()
        if lock
        else db.session.get(cls, ident)
    )
    need(obj is not None, "NOT_FOUND", "Không tìm thấy hồ sơ", 404)
    return obj


def enrollment(cid, uid=None, active=True):
    q = CourseEnrollment.query.filter_by(
        course_id=cid, user_id=uid or current_user().id
    )
    if active:
        q = q.filter_by(status="active")
    return q.first()


def course(cid, staff=False, coordinator=False):
    need(current_user().role != "admin", "FORBIDDEN", "Tài khoản admin chỉ quản trị hệ thống, không thao tác nghiệp vụ học tập", 403)
    c = get(CourseOffering, cid)
    e = enrollment(cid)
    need(e is not None, "NOT_FOUND", "Không tìm thấy lớp học phần", 404)
    if staff:
        need(e.role in STAFF, "FORBIDDEN", "Cần quyền giảng viên phụ trách", 403)
    if coordinator:
        need(e.role in STAFF, "FORBIDDEN", "Cần quyền giảng viên", 403)
    return c


def assignment(aid, staff=False):
    a = get(Assignment, aid)
    course(a.course_id, staff=staff)
    need(enrollment(a.course_id).role in STAFF or not a.is_hidden,"NOT_FOUND","Đề bài chưa được công bố hoặc đang được ẩn",404)
    return a


def membership(pid, uid=None):
    return AssignmentMembership.query.filter_by(
        project_id=pid, user_id=uid or current_user().id, status="active"
    ).first()


def project(pid, manage=False, staff=False, mutable=False):
    need(current_user().role != "admin", "FORBIDDEN", "Tài khoản admin chỉ quản trị hệ thống, không truy cập nghiệp vụ dự án", 403)
    p = get(Project, pid, lock=mutable and request.method != "GET")
    need(p.mode == "academic", "NOT_FOUND", "Không tìm thấy dự án học thuật", 404)
    a = get(Assignment, p.assignment_id)
    e = enrollment(a.course_id)
    need(e and (e.role in STAFF or not a.is_hidden),"NOT_FOUND","Đề bài chưa được công bố hoặc đang được ẩn",404)
    m = membership(pid)
    need(
        e is not None and (e.role in STAFF or m is not None),
        "NOT_FOUND",
        "Không tìm thấy dự án",
        404,
    )
    if staff:
        need(e.role in STAFF, "FORBIDDEN", "Cần quyền giảng viên phụ trách", 403)
    if manage:
        need(
            m is not None and m.role == "leader",
            "FORBIDDEN",
            "Chỉ nhóm trưởng mới được thay đổi dự án",
            403,
        )
    if mutable:
        need(
            get(CourseOffering, a.course_id).status not in ("closed", "archived"),
            "FINALIZED_LOCKED",
            "Lớp học phần đã khóa",
            409,
        )
        need(
            p.status not in ("finalized", "archived"),
            "FINALIZED_LOCKED",
            "Hồ sơ đã khóa",
            409,
        )
        need(
            a.status not in ("closed", "archived"),
            "FINALIZED_LOCKED",
            "Đề bài đã khóa",
            409,
        )
    return p


def task(tid, **kw):
    t = get(Task, tid, lock=request.method != "GET")
    project(t.project_id, **kw)
    return t


def participant(t, uid=None):
    uid = uid or current_user().id
    p = get(Project, t.project_id)
    a = get(Assignment, p.assignment_id)
    need(
        enrollment(a.course_id, uid) is not None
        and enrollment(a.course_id, uid).role == "student"
        and membership(t.project_id, uid)
        and TaskParticipant.query.filter_by(task_id=t.id, user_id=uid).first(),
        "INVALID_PARTICIPANT",
        "Chỉ sinh viên được phân công trong nhóm mới được thực hiện nhiệm vụ",
        403,
    )


def is_staff(p):
    return enrollment(get(Assignment, p.assignment_id).course_id).role in STAFF


def version(obj, body=None):
    body = body if body is not None else json_body()
    need("version" in body, "VERSION_REQUIRED", "Cần phiên bản dữ liệu", 400)
    need(
        type(body["version"]) is int and obj.version == body["version"],
        "VERSION_CONFLICT",
        "Dữ liệu đã thay đổi. Tải bản mới để tiếp tục",
        409,
    )
    obj.version += 1


def state(obj, states):
    need(
        obj.status in states,
        "INVALID_TRANSITION",
        "Trạng thái hiện tại không cho phép thao tác này",
        409,
    )


def dto(obj, omit=()):
    result = {}
    for col in obj.__table__.columns:
        key = col.name
        if key in omit or key in ("storage_key", "password_hash"):
            continue
        value = getattr(obj, key)
        if isinstance(value, Decimal):
            value = format(value, ".2f")
        elif isinstance(value, datetime):
            value = iso(value)
        result[key] = value
    return result


def user_brief(uid):
    u = db.session.get(User, uid)
    return {"id": uid, "full_name": u.full_name} if u else None


def paginate(query, render=dto, prefetch=None):
    try:
        page = max(1, int(request.args.get("page", 1)))
        size = max(1, min(100, int(request.args.get("page_size", 20))))
    except ValueError:
        need(False)
    entries = query.offset((page - 1) * size).limit(size).all()
    if prefetch:
        prefetch(entries)
    return {
        "items": [render(x) for x in entries],
        "page": page,
        "page_size": size,
        "total": query.order_by(None).count(),
    }


def rows(cls, **kw):
    return [dto(x) for x in cls.query.filter_by(**kw).order_by(cls.id)]


def audit(action, obj, cid=None, pid=None, reason=None):
    db.session.flush()
    ev = AuditEvent(
        actor_id=current_user().id if current_user() else None,
        action=action,
        entity_type=obj.__tablename__,
        entity_id=obj.id,
        course_id=cid,
        project_id=pid,
        request_id=getattr(g, "request_id", uuid.uuid4().hex),
        reason=reason,
        before_json={},
        after_json={
            "version": getattr(obj, "version", 1),
            "status": getattr(obj, "status", None),
        },
        created_at=now(),
    )
    db.session.add(ev)


def notify(event, obj, recipients, path):
    db.session.flush()
    if not (event.startswith("help.") or event == "group.invited"):
        pid = obj.id if isinstance(obj, Project) else getattr(obj, "project_id", None)
        if not pid and getattr(obj, "task_id", None):
            pid = get(Task, obj.task_id).project_id
        if pid:
            cid = get(Assignment, get(Project, pid).assignment_id).course_id
            recipients = [
                uid
                for uid in recipients
                if not (
                    enrollment(cid, uid) and enrollment(cid, uid).role == "instructor"
                )
            ]
    db.session.add(
        OutboxEvent(
            event_type=event,
            aggregate_id=obj.id,
            payload={
                "recipients": list(set(recipients)),
                "path": path,
                "subject": getattr(obj, "subject", None)
                or getattr(obj, "title", None)
                or (
                    get(Task, obj.task_id).title
                    if getattr(obj, "task_id", None)
                    else "Nhóm của bạn có nội dung cần theo dõi."
                ),
            },
            created_at=now(),
        )
    )


def command(idempotent=False):
    def deco(fn):
        @functools.wraps(fn)
        def wrapped(*args, **kwargs):
            need(current_user() is not None, "UNAUTHORIZED", "Bạn cần đăng nhập", 401)
            if request.method == "GET":
                return jsonify(data=fn(*args, **kwargs))
            try:
                key = request.headers.get("Idempotency-Key")
                if idempotent:
                    need(
                        key and len(key) <= 128,
                        "IDEMPOTENCY_KEY_REQUIRED",
                        "Cần mã yêu cầu chống gửi trùng",
                    )
                record = None
                if key:
                    if db.engine.dialect.name == "postgresql":
                        lock_key = int.from_bytes(
                            hashlib.sha256(
                                f"{current_user().id}:{request.path}:{key}".encode()
                            ).digest()[:8],
                            "big",
                            signed=True,
                        )
                        db.session.execute(
                            sqltext("SELECT pg_advisory_xact_lock(:key)"),
                            {"key": lock_key},
                        )
                    digest = hashlib.sha256(request.get_data()).hexdigest()
                    record = IdempotencyRecord.query.filter_by(
                        actor_id=current_user().id, route=request.path, key=key
                    ).first()
                    if record:
                        authorize_replay()
                        need(
                            record.request_hash == digest,
                            "IDEMPOTENCY_CONFLICT",
                            "Mã yêu cầu đã được dùng với nội dung khác",
                            409,
                        )
                        return jsonify(record.response_body), record.response_status
                value = fn(*args, **kwargs)
                status = 200
                if isinstance(value, tuple):
                    value, status = value
                body = {"data": value}
                if key:
                    db.session.add(
                        IdempotencyRecord(
                            actor_id=current_user().id,
                            route=request.path,
                            key=key,
                            request_hash=digest,
                            response_status=status,
                            response_body=body,
                            expires_at=now() + timedelta(hours=48),
                        )
                    )
                db.session.commit()
                return jsonify(body), status
            except StaleDataError:
                db.session.rollback()
                fail(
                    409,
                    "VERSION_CONFLICT",
                    "Dữ liệu đã thay đổi. Tải bản mới để tiếp tục",
                )
            except IntegrityError:
                db.session.rollback()
                fail(
                    409,
                    "DATA_CONFLICT",
                    "Dữ liệu đã tồn tại hoặc có cập nhật đồng thời",
                )
            except Exception:
                db.session.rollback()
                raise

        wrapped.idempotent_required = idempotent
        return wrapped

    return deco


def evidence_refs(refs, t=None, a=None, required=True):
    need(
        isinstance(refs, list) and (bool(refs) or not required),
        "EVIDENCE_REQUIRED",
        "Cần dẫn căn cứ",
    )
    for ref in refs:
        need(isinstance(ref, dict))
        if ref.get("direct_verification") and t is None:
            need(
                isinstance(ref["direct_verification"], str)
                and len(ref["direct_verification"].strip()) >= 10
            )
            continue
        rev = get(EvidenceRevision, ref.get("revision_id", 0))
        rt = get(Task, rev.task_id)
        need(
            (not t or t.id == rt.id)
            and (not a or get(Project, rt.project_id).assignment_id == a.id),
            "INVALID_EVIDENCE_SCOPE",
            "Minh chứng không thuộc phạm vi này",
        )
        project(rt.project_id)
        aid = ref.get("asset_id")
        if aid:
            need(
                db.session.get(EvidenceRevisionAsset, (rev.id, aid)) is not None,
                "INVALID_EVIDENCE_SCOPE",
                "File không thuộc phiên bản",
            )
        need(
            isinstance(ref.get("locator"), str) and bool(ref["locator"].strip()),
            message="Cần ghi vị trí nội dung minh chứng",
        )
    return refs


def task_dto(t):
    d = dto(t)
    d["participants"] = [
        {**dto(x), "user": user_brief(x.user_id)}
        for x in related(TaskParticipant, task_id=t.id)
    ]
    d["criteria"] = [
        dto(get(Criterion, x.criterion_id))
        for x in related(TaskCriterion, task_id=t.id)
    ]
    d["submissions"] = [
        {
            **dto(x),
            "late": x.received_at > x.submitted_due_at,
            "submitted_by_name": user_brief(x.submitted_by)["full_name"],
            "self_review": x.reviewed_by == x.submitted_by,
            "participant_names": [
                user_brief(uid)["full_name"] for uid in x.participant_ids
            ],
        }
        for x in sorted(
            related(TaskSubmission, task_id=t.id), key=lambda s: s.attempt_no
        )
    ]
    d["revisions"] = [
        revision_dto(x)
        for x in sorted(
            related(EvidenceRevision, task_id=t.id), key=lambda r: r.revision_no
        )
    ]
    from .evidence import submission_extras
    by_id = {x.id: x for x in related(TaskSubmission, task_id=t.id)}
    for x in d["submissions"]:
        x.update(submission_extras(by_id[x["id"]], t))
    if is_staff(get(Project,t.project_id)):
        submitted={x["revision_id"] for x in d["submissions"]}
        d["revisions"]=[r for r in d["revisions"] if r["id"] in submitted]
        d["assets"]=[]
    else:
        d["assets"] = [asset_dto(x) for x in related(EvidenceAsset, task_id=t.id)]
    d["checkins"] = [dto(x) for x in related(ProgressCheckin, task_id=t.id)]
    titles = {
        "task.created": "Tạo công việc",
        "task.started": "Bắt đầu thực hiện",
        "task.updated": "Cập nhật công việc",
        "task.submitted": "Gửi duyệt",
        "submission.accepted": "Duyệt hoàn thành",
        "submission.returned": "Yêu cầu sửa",
        "submission.referred": "Chuyển bản nộp cho giảng viên",
    }
    submission_ids = [x["id"] for x in d["submissions"]]
    events = (
        AuditEvent.query.filter(AuditEvent.project_id == t.project_id)
        .filter(
            db.or_(
                db.and_(AuditEvent.entity_type == "task", AuditEvent.entity_id == t.id),
                db.and_(
                    AuditEvent.entity_type == "task_submission",
                    AuditEvent.entity_id.in_(submission_ids),
                ),
            )
        )
        .all()
    )
    d["timeline"] = sorted(
        [
            {
                "title": titles.get(e.action, "Cập nhật công việc"),
                "content": e.reason or "",
                "created_at": iso(e.created_at),
                "sequence": e.id,
            }
            for e in events
            if e.action in titles
        ]
        + [
            {
                "title": "Cập nhật tiến độ",
                "content": x["content"],
                "created_at": x["created_at"],
            }
            for x in d["checkins"]
        ],
        key=lambda e: (e["created_at"], e.get("sequence", 0)),
        reverse=True,
    )
    return d


def asset_dto(x):
    d = dto(x)
    d["download_url"] = f"/api/v1/assets/{x.id}/download" if x.kind == "file" else x.url
    return d


def revision_dto(x):
    return {
        **dto(x),
        "assets": [
            asset_dto(get(EvidenceAsset, r.asset_id))
            for r in EvidenceRevisionAsset.query.filter_by(revision_id=x.id)
        ],
    }


def claim_dto(c):
    return {
        **dto(c),
        "user": user_brief(c.user_id),
        "history": [
            {**dto(r), "responses": rows(ContributionResponse, claim_revision_id=r.id)}
            for r in ClaimRevision.query.filter_by(claim_id=c.id).order_by(
                ClaimRevision.revision
            )
        ],
        "decisions": rows(DisputeDecision, claim_id=c.id),
    }


def authorize_replay():
    """Revoked assignments cannot recover cached command DTOs with old keys."""
    from ..collab.privacy import authorize_teamwork_replay
    authorize_teamwork_replay()
    parts = request.path.removeprefix("/api/v1/").split("/")
    if parts[0] == "workflow":
        from ..models.workflow import GroupDeparture
        if len(parts)>2 and parts[2].isdigit():
            ident=int(parts[2])
            if parts[1]=="projects": project(ident)
            elif parts[1]=="tasks": task(ident)
            elif parts[1]=="departures": project(get(GroupDeparture,ident).project_id)
            elif parts[1]=="assignments": assignment(ident,staff=True)
        elif len(parts)>1 and parts[1]=="admin": need(current_user().role=="admin", "FORBIDDEN", "Cần quản trị",403)
        return
    if len(parts) < 2 or not parts[1].isdigit():
        return
    kind, ident = parts[0], int(parts[1])
    if kind == "courses":
        course(ident)
    elif kind == "assignments":
        assignment(ident,staff="evaluation-rounds" in parts)
    elif kind == "projects":
        project(ident)
    elif kind == "tasks":
        task(ident)
    elif kind == "submissions":
        task(get(TaskSubmission, ident).task_id)
    elif kind == "complaints":
        task(get(WorkComplaint, ident).task_id)
    elif kind == "invitations":
        inv = get(GroupInvitation, ident)
        need(
            inv.user_id == current_user().id, "NOT_FOUND", "Không tìm thấy lời mời", 404
        )
        assignment(get(Project, inv.project_id).assignment_id)
    elif kind == "claims":
        task(get(ContributionClaim, ident).task_id)
    elif kind == "milestones":
        project(get(Milestone, ident).project_id)
    elif kind == "policies":
        assignment(get(AssessmentPolicy, ident).assignment_id, staff=True)
    elif kind == "imports":
        course(get(ImportBatch, ident).course_id, staff=True)
    elif kind == "enrollments":
        course(get(CourseEnrollment, ident).course_id, coordinator=True)
    elif kind == "evaluation-rounds":
        assignment(get(PeerRound, ident).assignment_id,staff=True)
    elif kind == "peer-rounds":
        assignment(get(PeerRound, ident).assignment_id)
    elif kind == "assessment-cycles":
        assignment(get(AssessmentCycle, ident).assignment_id, staff=True)
    elif kind == "assessment-records":
        r = get(AssessmentRecord, ident)
        if r.student_id != current_user().id:
            project(r.project_id, staff=True)
    elif kind == "appeals":
        a = get(Appeal, ident)
        if a.student_id != current_user().id:
            project(
                get(AssessmentRecord, a.assessment_record_id).project_id, staff=True
            )
    elif kind == "exports":
        course(get(ExportBatch, ident).course_id, staff=True)
    elif kind in ("change-requests", "risk-cases", "help-requests"):
        cls = {
            "change-requests": ChangeRequest,
            "risk-cases": RiskCase,
            "help-requests": HelpRequest,
        }[kind]
        project(get(cls, ident).project_id)


def related(cls, **filters):
    key = (cls, tuple(filters.items()))
    cache = getattr(g, "task_related", {})
    return cache[key] if key in cache else cls.query.filter_by(**filters).all()


def prefetch_tasks(tasks, detailed=False):
    if not tasks:
        return
    ids = [t.id for t in tasks]
    cache = {}
    objects = []
    uids = set()
    for cls in (
        (
            TaskParticipant,
            TaskCriterion,
            TaskSubmission,
            EvidenceRevision,
            EvidenceAsset,
            ProgressCheckin,
        )
        if detailed
        else (TaskParticipant, TaskCriterion, TaskSubmission)
    ):
        records = cls.query.filter(cls.task_id.in_(ids)).all()
        objects.extend(records)
        for tid in ids:
            cache[(cls, (("task_id", tid),))] = []
        for r in records:
            cache[(cls, (("task_id", r.task_id),))].append(r)
            if cls is TaskParticipant:
                uids.add(r.user_id)
            if cls is TaskSubmission:
                uids.add(r.submitted_by)
    objects.extend(User.query.filter(User.id.in_(uids)).all())
    criterion_ids = [x.criterion_id for x in objects if isinstance(x, TaskCriterion)]
    objects.extend(Criterion.query.filter(Criterion.id.in_(criterion_ids)).all())
    g.task_related = cache
    g.prefetched_objects = objects


def latest_status(t):
    if not t.latest_submission_id:
        return None
    s = next((x for x in related(TaskSubmission, task_id=t.id) if x.id == t.latest_submission_id), None)
    return s.status if s else None


def task_summary(t):
    return {
        "id": t.id,
        "project_id": t.project_id,
        "milestone_id": t.milestone_id,
        "title": t.title,
        "description": t.description,
        "status": t.status,
        "priority": t.priority,
        "due_at": iso(t.due_at),
        "original_due_at": iso(t.original_due_at),
        "points": t.points,
        "version": t.version,
        "latest_submission_id": t.latest_submission_id,
        "latest_submission_status": latest_status(t),
        "return_count": sum(s.status == "returned" for s in related(TaskSubmission, task_id=t.id)),
        "overdue": t.status in ("todo", "in_progress") and t.due_at < now(),
        "participants": [
            {"user_id": x.user_id, "role": x.role, "user": user_brief(x.user_id)}
            for x in related(TaskParticipant, task_id=t.id)
        ],
        "criteria": [
            {"id": x.criterion_id, "title": get(Criterion, x.criterion_id).title}
            for x in related(TaskCriterion, task_id=t.id)
        ],
    }


def personal_evidence_scope(t, asset=None, revision=None):
    """Former members retain their own uploaded or explicitly claimed evidence."""
    p = get(Project, t.project_id)
    a = get(Assignment, p.assignment_id)
    uid = current_user().id
    e = enrollment(a.course_id, active=False)
    m = membership(p.id)
    if e and e.status == "active" and e.role in STAFF:
        approved={x.revision_id for x in TaskSubmission.query.filter_by(task_id=t.id)}
        visible=revision and revision.id in approved
        if asset:
            visible=EvidenceRevisionAsset.query.filter(EvidenceRevisionAsset.revision_id.in_(approved),EvidenceRevisionAsset.asset_id==asset.id).first() is not None
        need(visible,"FORBIDDEN","Tài liệu chưa được nộp",403)
        return
    if e and e.status == "active" and m:
        return
    history = (
        AssignmentMembership.query.filter_by(project_id=p.id, user_id=uid)
        .order_by(AssignmentMembership.id.desc())
        .first()
    )
    cutoff = (
        history.left_at if history and history.left_at else (e.left_at if e else None)
    )
    need(history and cutoff, "NOT_FOUND", "Không tìm thấy minh chứng", 404)
    claims = ContributionClaim.query.filter_by(task_id=t.id, user_id=uid).all()
    refs = []
    for c in claims:
        for r in ClaimRevision.query.filter_by(claim_id=c.id):
            refs.extend(r.evidence_refs)
    if asset:
        claimed = any(
            (ref.get("asset_id") == asset.id)
            or (
                ref.get("revision_id")
                and db.session.get(
                    EvidenceRevisionAsset, (ref["revision_id"], asset.id)
                )
            )
            for ref in refs
        )
        need(
            asset.created_at <= cutoff and (asset.uploaded_by == uid or claimed),
            "NOT_FOUND",
            "Không tìm thấy minh chứng cá nhân",
            404,
        )
    elif revision:
        need(
            revision.created_at <= cutoff
            and (
                revision.created_by == uid
                or any(ref.get("revision_id") == revision.id for ref in refs)
            ),
            "NOT_FOUND",
            "Không tìm thấy phiên bản cá nhân",
            404,
        )
