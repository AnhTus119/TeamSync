"""M20/M06/M17 collaboration records. Internal and published files have separate entries."""
from ..extensions import db
from .academic import Entity, fk, D, S, I, T, J


class UserPreference(db.Model):
    __tablename__ = 'user_preference'
    user_id = fk('user', primary_key=True)
    theme = db.Column(S(10), nullable=False, default='system')
    accent = db.Column(S(7), nullable=False, default='#6658e8')
    __table_args__ = (db.CheckConstraint("theme IN ('system','light','dark')"),)


class TaskBranch(Entity, db.Model):
    __tablename__ = 'task_branch'
    task_id = fk('task', nullable=False, index=True)
    author_id = fk('user', nullable=False)
    name = db.Column(S(100), nullable=False)
    status = db.Column(S(20), nullable=False, default='open')
    __table_args__ = (db.UniqueConstraint('task_id', 'name'),)


class BranchMergeRequest(Entity, db.Model):
    """TaskSubmission is the versioned MR; this binds it to its task branch."""
    __tablename__ = 'branch_merge_request'
    branch_id = fk('task_branch', nullable=False, index=True)
    submission_id = fk('task_submission', nullable=False, unique=True)


class Vault(Entity, db.Model):
    __tablename__ = 'vault'
    project_id = fk('project', nullable=False)
    kind = db.Column(S(12), nullable=False)
    __table_args__ = (db.UniqueConstraint('project_id', 'kind'),
                      db.CheckConstraint("kind IN ('internal','final')"))


class StoredFile(Entity, db.Model):
    __tablename__ = 'stored_file'
    project_id = fk('project', nullable=False, index=True)
    uploaded_by = fk('user', nullable=False)
    kind = db.Column(S(12), nullable=False)
    storage_key = db.Column(S(255))
    original_filename = db.Column(S(255))
    mime_type = db.Column(S(120))
    size_bytes = db.Column(I, nullable=False, default=0)
    sha256 = db.Column(S(64))
    url = db.Column(T)


class VaultEntry(Entity, db.Model):
    __tablename__ = 'vault_entry'
    vault_id = fk('vault', nullable=False, index=True)
    file_id = fk('stored_file', nullable=False)
    submitted_by = fk('user', nullable=False)
    title = db.Column(S(240), nullable=False)
    note = db.Column(T, nullable=False, default='')
    __table_args__ = (db.UniqueConstraint('vault_id', 'file_id'),)


class Message(Entity, db.Model):
    __tablename__ = 'team_message'
    project_id = fk('project', nullable=False)
    sender_id = fk('user', nullable=False)
    content = db.Column(T, nullable=False)
    file_ids = db.Column(J, nullable=False, default=list)
    client_key = db.Column(S(80), nullable=False)
    kind = db.Column(S(12), nullable=False, default='chat')
    __table_args__ = (db.UniqueConstraint('project_id', 'sender_id', 'client_key'),
                      db.Index('ix_message_cursor', 'project_id', 'id'))


class Meeting(Entity, db.Model):
    __tablename__ = 'team_meeting'
    project_id = fk('project', nullable=False, index=True)
    host_id = fk('user', nullable=False)
    title = db.Column(S(200), nullable=False)
    room_name = db.Column(S(100), nullable=False, unique=True)
    status = db.Column(S(12), nullable=False, default='open')
    notes = db.Column(T, nullable=False, default='')
    ended_at = db.Column(D())


class MeetingAttendance(Entity, db.Model):
    __tablename__ = 'meeting_attendance'
    meeting_id = fk('team_meeting', nullable=False)
    user_id = fk('user', nullable=False)
    joined_at = db.Column(D(), nullable=False)
    last_seen_at = db.Column(D(), nullable=False)
    active_seconds = db.Column(I, nullable=False, default=0)
    __table_args__ = (db.UniqueConstraint('meeting_id', 'user_id'),)


class MeetingTaskDraft(Entity, db.Model):
    __tablename__ = 'meeting_task_draft'
    meeting_id = fk('team_meeting', nullable=False)
    title = db.Column(S(200), nullable=False)
    source_line = db.Column(T, nullable=False)
    source_hash = db.Column(S(64), nullable=False)
    status = db.Column(S(15), nullable=False, default='draft')
    task_id = fk('task')
    __table_args__ = (db.UniqueConstraint('meeting_id', 'source_hash'),)


class DeadlineExtension(Entity, db.Model):
    __tablename__ = 'deadline_extension'
    task_id = fk('task', nullable=False, index=True)
    requested_by = fk('user', nullable=False)
    reason = db.Column(T, nullable=False)
    old_due_at = db.Column(D(), nullable=False)
    requested_due_at = db.Column(D(), nullable=False)
    status = db.Column(S(12), nullable=False, default='pending')
    decided_by = fk('user')
    decision_reason = db.Column(T)
    decided_at = db.Column(D())


class CommitmentLog(Entity, db.Model):
    __tablename__ = 'commitment_log'
    project_id = fk('project', nullable=False)
    user_id = fk('user', nullable=False)
    period = db.Column(S(10), nullable=False)
    algorithm = db.Column(S(20), nullable=False, default='ci-v1')
    score = db.Column(db.Float)
    metrics = db.Column(J, nullable=False)
    __table_args__ = (db.UniqueConstraint('project_id','user_id','period','algorithm'),
                     db.CheckConstraint('score IS NULL OR (score >= 0 AND score <= 100)'))


class TeamAlert(Entity, db.Model):
    __tablename__ = 'team_alert'
    project_id = fk('project', nullable=False, index=True)
    subject_key = db.Column(S(100), nullable=False, unique=True)
    rule = db.Column(S(20), nullable=False)
    user_id = fk('user')
    task_id = fk('task')
    status = db.Column(S(12), nullable=False, default='open')
    message = db.Column(S(240), nullable=False)
    last_ping_at = db.Column(D())


class MatrixReview(Entity, db.Model):
    __tablename__ = 'matrix_review'
    round_id = fk('peer_round', nullable=False)
    project_id = fk('project', nullable=False)
    reviewer_id = fk('user', nullable=False)
    reviewee_id = fk('user', nullable=False)
    attitude = db.Column(I, nullable=False)
    quality = db.Column(I, nullable=False)
    # Original columns remain for compatibility; these preserve every 1–10 value.
    attitude10 = db.Column(I)
    quality10 = db.Column(I)
    comment = db.Column(T, nullable=False, default='')
    __table_args__ = (db.UniqueConstraint('round_id','reviewer_id','reviewee_id'),
                     db.CheckConstraint('reviewer_id != reviewee_id'),
                     db.CheckConstraint('attitude BETWEEN 1 AND 5'),
                     db.CheckConstraint('quality BETWEEN 1 AND 5'),
                     db.CheckConstraint('attitude10 IS NULL OR attitude10 BETWEEN 1 AND 10'),
                     db.CheckConstraint('quality10 IS NULL OR quality10 BETWEEN 1 AND 10'))


from sqlalchemy import event
for cls in (StoredFile, VaultEntry, CommitmentLog):
    def immutable_collaboration(mapper, connection, target):
        raise ValueError("Immutable collaboration record")
    event.listen(cls, 'before_update', immutable_collaboration)
    event.listen(cls, 'before_delete', immutable_collaboration)


class AcademicGrade(Entity, db.Model):
    """Teacher's explicit decision, never a machine-generated grade."""
    __tablename__ = 'academic_grade'
    project_id = fk('project', nullable=False)
    student_id = fk('user', nullable=False)
    assessor_id = fk('user', nullable=False)
    revision = db.Column(I, nullable=False)
    score = db.Column(db.Numeric(4, 2), nullable=False)
    rationale = db.Column(T, nullable=False)
    context_json = db.Column(J, nullable=False)
    __table_args__ = (db.UniqueConstraint('project_id','student_id','revision'),
                     db.CheckConstraint('score >= 0 AND score <= 10'))


event.listen(AcademicGrade, 'before_update', immutable_collaboration)
event.listen(AcademicGrade, 'before_delete', immutable_collaboration)
