"""Separate worker, transaction-scoped scheduler exclusion and retryable outbox."""

from contextlib import contextmanager
from datetime import timedelta
import os, time

try:
    import fcntl
except ImportError:  # Windows development
    fcntl = None
    import msvcrt
from pathlib import Path
from flask import current_app
from sqlalchemy import text
from ..extensions import db
from ..common.clock import now
from ..models.academic import OutboxEvent, Notification


@contextmanager
def risk_lock():
    if db.engine.dialect.name == "postgresql":
        acquired = db.session.execute(
            text("SELECT pg_try_advisory_xact_lock(742519)")
        ).scalar()
        yield bool(acquired)
    else:
        path = Path(current_app.instance_path) / "risk-worker.lock"
        f = path.open("a+")
        try:
            try:
                if fcntl:
                    fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
                else:
                    f.seek(0)
                    f.write("0")
                    f.flush()
                    f.seek(0)
                    msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
                locked = True
            except OSError:
                locked = False
            yield locked
        finally:
            f.close()


def dispatch_outbox():
    events = (
        OutboxEvent.query.filter(
            OutboxEvent.processed_at == None,
            db.or_(
                OutboxEvent.next_attempt_at == None,
                OutboxEvent.next_attempt_at <= now(),
            ),
        )
        .order_by(OutboxEvent.id)
        .limit(100)
        .with_for_update(skip_locked=True)
        .all()
    )
    count = 0
    for e in events:
        try:
            with db.session.begin_nested():
                for uid in e.payload.get("recipients", []):
                    if not Notification.query.filter_by(
                        recipient_id=uid, event_id=e.id
                    ).first():
                        db.session.add(
                            Notification(
                                recipient_id=uid,
                                event_id=e.id,
                                title={
                                    "group.invited": "Lời mời tham gia nhóm",
                                    "group.invitation_responded": "Lời mời nhóm có phản hồi",
                                    "submission.pending": "Có bản nộp chờ duyệt",
                                    "submission.reviewed": "Bản nộp đã có kết quả",
                                    "help.requested": "Nhóm cần trợ giúp",
                                    "help.responded": "Giảng viên đã phản hồi",
                                    "help.complaint": "Cần hỗ trợ giải quyết phản ánh",
                                    "contribution.complained": "Có phản ánh đóng góp",
                                    "contribution.resolved": "Đã xử lý phản ánh đóng góp",
                                    "risk.opened": "Công việc cần chú ý",
                                }.get(e.event_type, "Nhóm có cập nhật"),
                                body=e.payload.get(
                                    "subject", "Mở hồ sơ để xem nội dung."
                                ),
                                target_path=e.payload.get("path", "/home"),
                            )
                        )
                e.processed_at = now()
                count += 1
        except Exception:
            e.attempts += 1
            e.next_attempt_at = now() + timedelta(
                seconds=min(3600, 2 ** min(e.attempts, 10))
            )
    db.session.commit()
    return count


def evaluate_all(course_code=None):
    from ..models import Project
    from ..models.academic import Assignment, CourseOffering
    from ..m17_reports.academic_services import evaluate_project

    count = 0
    with risk_lock() as acquired:
        if not acquired:
            return 0
        q = Project.query.filter(
            Project.mode == "academic", Project.status.in_(["active", "assessment"])
        )
        if course_code:
            q = (
                q.join(Assignment, Assignment.id == Project.assignment_id)
                .join(CourseOffering, CourseOffering.id == Assignment.course_id)
                .filter(CourseOffering.code == course_code)
            )
        for p in q.all():
            try:
                with db.session.begin_nested():
                    count += evaluate_project(p)
            except Exception:
                current_app.logger.error("Risk evaluation failed project_id=%s", p.id)
        db.session.commit()
    return count
