"""Small durable records for group departures, reports and deadline deduplication."""
from .academic import Entity, fk, db, S, T, J, D

class GroupDeparture(Entity, db.Model):
    __tablename__ = 'group_departure'
    project_id = fk('project', nullable=False)
    user_id = fk('user', nullable=False)
    reason = db.Column(T, nullable=False)
    status = db.Column(S(20), nullable=False, default='pending')
    leader_exit = db.Column(db.Boolean, nullable=False)
    electorate = db.Column(J, nullable=False, default=list)
    votes = db.Column(J, nullable=False, default=dict)
    threshold = db.Column(db.Integer, nullable=False)
    successor_id = fk('user')
    resolved_at = db.Column(D())

class ReportSnapshot(Entity, db.Model):
    __tablename__ = 'report_snapshot'
    project_id = fk('project', nullable=False)
    created_by = fk('user', nullable=False)
    content = db.Column(J, nullable=False)

class DeadlineReminder(db.Model):
    __tablename__ = 'deadline_reminder'
    key = db.Column(S(180), primary_key=True)

class GroupDelivery(Entity, db.Model):
    __tablename__ = 'group_delivery'
    project_id = fk('project', nullable=False)
    submitted_by = fk('user', nullable=False)
    title = db.Column(S(200), nullable=False)
    submission_ids = db.Column(J, nullable=False)

class EvidenceCriterion(Entity, db.Model):
    """Evidence checklist item owned by an assignment; hidden items keep history."""
    __tablename__ = 'evidence_criterion'
    __table_args__ = (db.Index('ix_evidence_criterion_assignment', 'assignment_id', 'is_active'),)
    assignment_id = fk('assignment', nullable=False)
    title = db.Column(S(200), nullable=False)
    description = db.Column(T, nullable=False, default='')
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_by = fk('user', nullable=False)

class SubmissionEvidence(Entity, db.Model):
    """A file/link of one exact submission attached to one criterion."""
    __tablename__ = 'submission_evidence'
    __table_args__ = (db.UniqueConstraint('submission_id', 'criterion_id', 'asset_id'),
                      db.Index('ix_submission_evidence_criterion', 'criterion_id'))
    submission_id = fk('task_submission', nullable=False)
    criterion_id = fk('evidence_criterion', nullable=False)
    asset_id = fk('evidence_asset', nullable=False)

class SubmissionReferral(Entity, db.Model):
    """Leader hands one exact submission to the course instructor for review."""
    __tablename__ = 'submission_referral'
    __table_args__ = (db.Index('ix_submission_referral_instructor', 'instructor_id', 'status'),)
    submission_id = fk('task_submission', nullable=False, unique=True)
    project_id = fk('project', nullable=False)
    referred_by = fk('user', nullable=False)
    instructor_id = fk('user', nullable=False)
    reason = db.Column(T, nullable=False)
    status = db.Column(S(20), nullable=False, default='open')
    decided_at = db.Column(D())

class ScheduleItem(Entity, db.Model):
    """Timeline entry created by a user; optionally shared read-only with one project's members."""
    __tablename__ = 'schedule_item'
    __table_args__ = (db.Index('ix_schedule_owner_dates', 'owner_id', 'start_date'),
                      db.Index('ix_schedule_project_dates', 'project_id', 'start_date'))
    owner_id = fk('user', nullable=False)
    project_id = fk('project')
    title = db.Column(S(200), nullable=False)
    note = db.Column(T, nullable=False, default='')
    category = db.Column(S(20), nullable=False, default='other')
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
