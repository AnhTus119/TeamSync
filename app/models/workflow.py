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
