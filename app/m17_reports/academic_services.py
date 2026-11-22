"""Explainable progress alerts; alerts do not deduct points."""

from datetime import timedelta
from ..academic.core import *


def risk_facts(t, at):
    """Pure rules receive explicit time and facts extracted from this task."""
    submissions = TaskSubmission.query.filter_by(task_id=t.id).all()
    pending = next((x for x in submissions if x.status == "pending"), None)
    facts = {
        "status": t.status,
        "due_at": t.due_at,
        "last_progress_at": t.last_progress_at,
        "created_at": (
            t.created_at.replace(tzinfo=timezone.utc)
            if t.created_at.tzinfo is None
            else t.created_at
        ),
        "has_submission": bool(submissions),
        "pending_at": pending.received_at if pending else None,
        "return_count": sum(x.status == "returned" for x in submissions),
    }
    return risk_rules(facts, at)


def risk_rules(f, at):
    result = {}
    due = f["due_at"]
    status = f["status"]
    if status == "done" or due is None:
        return result
    hours = (due - at).total_seconds() / 3600
    if status == "todo" and 0 <= hours <= 48:
        result["NEAR_DUE_NOT_STARTED"] = {
            "severity": "medium",
            "message": "Sắp đến hạn nhưng chưa bắt đầu",
            "hours_remaining": round(hours, 2),
        }
    if at > due and not f["has_submission"]:
        result["OVERDUE"] = {
            "severity": "high",
            "message": "Chưa có bản nộp và đã quá hạn",
            "due_at": iso(due),
        }
    last = f.get("last_progress_at") or f["created_at"]
    if status == "in_progress" and at - last >= timedelta(hours=72):
        result["STALE_PROGRESS"] = {
            "severity": "medium",
            "message": "72 giờ chưa có minh chứng hoặc cập nhật tiến độ có nội dung",
            "last_progress_at": iso(last),
        }
    if f["return_count"] >= 2:
        result["REPEATED_RETURN"] = {
            "severity": "medium",
            "message": "Cần hỗ trợ sau nhiều lần yêu cầu sửa",
            "returned_attempts": f["return_count"],
        }
    if f["pending_at"] and at - f["pending_at"] > timedelta(hours=48):
        result["REVIEW_WAITING"] = {
            "severity": "medium",
            "message": "Bản nộp chờ duyệt trên 48 giờ",
            "received_at": iso(f["pending_at"]),
        }
    return result


def evaluate_project(p):
    at = now()
    a = get(Assignment, p.assignment_id)
    instructor = (
        CourseEnrollment.query.filter_by(
            course_id=a.course_id, status="active", role="instructor"
        )
        .order_by(CourseEnrollment.id)
        .first()
    )
    teacher = instructor.user_id if instructor else None
    leader = AssignmentMembership.query.filter_by(
        project_id=p.id, status="active", role="leader"
    ).first()
    owner_id = leader.user_id if leader else p.created_by
    detected = {}
    for t in Task.query.filter_by(project_id=p.id):
        for code, reason in risk_facts(t, at).items():
            owner = owner_id if code == "REVIEW_WAITING" else t.primary_assignee_id
            detected[(f"task:{t.id}", code)] = (t.id, owner, reason)
    if a.due_at - at <= timedelta(hours=72) and p.status == "active":
        covered = set(
            db.session.scalars(
                db.select(TaskCriterion.criterion_id)
                .join(Task, Task.id == TaskCriterion.task_id)
                .join(TaskSubmission, TaskSubmission.task_id == Task.id)
                .where(Task.project_id == p.id)
            )
        )
        missing = [
            c.title
            for c in Criterion.query.filter_by(policy_id=a.published_policy_id)
            if c.id not in covered
        ]
        if missing:
            detected[(f"project:{p.id}", "EVIDENCE_GAP")] = (
                None,
                owner_id,
                {
                    "severity": "medium",
                    "message": "Chưa có bản nộp cho tiêu chí bắt buộc",
                    "missing_criteria": missing,
                },
            )
    open_cases = (
        RiskCase.query.filter_by(project_id=p.id)
        .filter(RiskCase.status.notin_(["resolved", "dismissed"]))
        .all()
    )
    existing = {(c.subject_key, c.rule_code): c for c in open_cases}
    for key, (tid, owner, reason) in detected.items():
        c = existing.get(key)
        if c:
            c.last_detected_at = at
            age = at - c.opened_at
            if (
                not c.escalated_at
                and teacher
                and (
                    (c.status == "new" and age >= timedelta(hours=24))
                    or (
                        c.status in ("new", "acknowledged")
                        and age >= timedelta(hours=48)
                    )
                )
            ):
                c.escalated_at = at
                audit("risk.escalated", c, pid=p.id)
        else:
            dismissed = (
                RiskCase.query.filter_by(
                    subject_key=key[0], rule_code=key[1], status="dismissed"
                )
                .order_by(RiskCase.episode_no.desc())
                .first()
            )
            if dismissed and dismissed.next_review_at and dismissed.next_review_at > at:
                continue
            episode = (
                db.session.query(db.func.max(RiskCase.episode_no))
                .filter_by(subject_key=key[0], rule_code=key[1])
                .scalar()
                or 0
            ) + 1
            c = RiskCase(
                project_id=p.id,
                task_id=tid,
                subject_key=key[0],
                rule_code=key[1],
                severity=reason["severity"],
                owner_id=owner,
                opened_at=at,
                last_detected_at=at,
                reason_json=reason,
                episode_no=episode,
            )
            db.session.add(c)
            audit("risk.opened", c, pid=p.id)
            notify("risk.opened", c, [owner] if owner else [], f"/risk-cases/{c.id}")
    for key, c in existing.items():
        if key not in detected:
            c.status = "resolved"
            c.resolved_at = at
            db.session.add(
                InterventionAction(
                    risk_case_id=c.id,
                    actor_id=teacher or p.created_by,
                    action_type="auto_resolved",
                    content="Điều kiện cảnh báo không còn sau lần kiểm tra",
                    completed_at=at,
                )
            )
            audit("risk.resolved", c, pid=p.id)
    db.session.flush()
    return len(detected)
