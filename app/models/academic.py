"""Academic records use restrictive FKs. Published evidence and snapshots are append-only."""

from sqlalchemy import event, inspect, text
from sqlalchemy.orm import declared_attr
from ..extensions import db
from ..common.clock import UTCDateTime, now

I = db.Integer
S = db.String
T = db.Text
J = db.JSON
D = UTCDateTime


def fk(table, **kw):
    opts = {k: kw.pop(k) for k in ("use_alter", "name") if k in kw}
    return db.Column(I, db.ForeignKey(table + ".id", ondelete="RESTRICT", **opts), **kw)


class Entity:
    id = db.Column(I, primary_key=True)
    created_at = db.Column(D(), nullable=False, default=now)
    updated_at = db.Column(D(), nullable=False, default=now, onupdate=now)
    version = db.Column(I, nullable=False, default=1)

    @declared_attr
    def __mapper_args__(cls):
        return {"version_id_col": cls.version}


class RuntimeSetting(db.Model):
    __tablename__ = "runtime_setting"
    key = db.Column(S(60), primary_key=True)
    value = db.Column(J, nullable=False)


class CourseOffering(Entity, db.Model):
    __tablename__ = "course_offering"
    __table_args__ = (db.UniqueConstraint("code", "term"),)
    code = db.Column(S(40), nullable=False)
    title = db.Column(S(200), nullable=False)
    term = db.Column(S(80), nullable=False)
    department_code = db.Column(S(40), default="")
    status = db.Column(S(20), nullable=False, default="draft")
    workspace_id = fk("workspace", nullable=False)
    created_by = fk("user", nullable=False)


class CourseEnrollment(Entity, db.Model):
    __tablename__ = "course_enrollment"
    __table_args__ = (
        db.UniqueConstraint("course_id", "user_id"),
        db.Index("ix_enrollment_scope", "course_id", "status"),
    )
    course_id = fk("course_offering", nullable=False)
    user_id = fk("user", nullable=False)
    role = db.Column(S(20), nullable=False, default="student")
    status = db.Column(S(20), nullable=False, default="active")
    student_code = db.Column(S(60))
    joined_at = db.Column(D(), nullable=False, default=now)
    left_at = db.Column(D())


class ExternalIdentity(Entity, db.Model):
    __tablename__ = "external_identity"
    __table_args__ = (db.UniqueConstraint("provider", "subject"),)
    user_id = fk("user", nullable=False)
    provider = db.Column(S(80), nullable=False)
    subject = db.Column(S(255), nullable=False)


class Assignment(Entity, db.Model):
    __tablename__ = "assignment"
    course_id = fk("course_offering", nullable=False)
    title = db.Column(S(200), nullable=False)
    brief = db.Column(T, nullable=False, default="")
    status = db.Column(S(20), nullable=False, default="draft")
    opens_at = db.Column(D())
    due_at = db.Column(D(), nullable=False)
    group_min = db.Column(I, nullable=False, default=1)
    group_max = db.Column(I, nullable=False, default=5)
    group_method = db.Column(S(20), nullable=False, default='random', server_default='random')
    is_hidden = db.Column(db.Boolean, nullable=False, default=False, server_default='0')
    group_mode = db.Column(S(16), nullable=False, default='self', server_default='self')
    formation_due_at = db.Column(D())
    published_policy_id = fk(
        "assessment_policy", use_alter=True, name="fk_assignment_policy"
    )


class AssessmentPolicy(Entity, db.Model):
    __tablename__ = "assessment_policy"
    __table_args__ = (db.UniqueConstraint("assignment_id", "revision"),)
    assignment_id = fk("assignment", nullable=False)
    revision = db.Column(I, nullable=False)
    status = db.Column(S(20), nullable=False, default="draft")
    scale_max = db.Column(db.Numeric(6, 2), nullable=False, default=10)
    appeal_window_hours = db.Column(I, nullable=False, default=72)
    peer_visibility = db.Column(S(80), default="instructor_identity_student_aggregate")
    late_rule = db.Column(S(40), default="record_only")
    policy_json = db.Column(J, nullable=False, default=dict)
    published_at = db.Column(D())


class Criterion(Entity, db.Model):
    __tablename__ = "criterion"
    __table_args__ = (
        db.UniqueConstraint("policy_id", "code"),
        db.CheckConstraint("weight > 0"),
        db.CheckConstraint("max_score > 0"),
    )
    policy_id = fk("assessment_policy", nullable=False)
    code = db.Column(S(30), nullable=False)
    title = db.Column(S(200), nullable=False)
    description = db.Column(T, default="")
    weight = db.Column(db.Numeric(6, 2), nullable=False)
    max_score = db.Column(db.Numeric(6, 2), nullable=False, default=10)
    evidence_requirement = db.Column(
        T, default="Minh chứng hoặc quyết định kiểm tra trực tiếp"
    )


class CriterionLevel(Entity, db.Model):
    __tablename__ = "criterion_level"
    criterion_id = fk("criterion", nullable=False)
    label = db.Column(S(80), nullable=False)
    score = db.Column(db.Numeric(6, 2), nullable=False)
    description = db.Column(T, nullable=False)
    ordinal = db.Column(I, nullable=False)


class AssignmentMembership(Entity, db.Model):
    __tablename__ = "assignment_membership"
    __table_args__ = (
        db.Index(
            "uq_active_assignment_member",
            "assignment_id",
            "user_id",
            unique=True,
            sqlite_where=text("status='active'"),
            postgresql_where=text("status='active'"),
        ),
    )
    assignment_id = fk("assignment", nullable=False)
    user_id = fk("user", nullable=False)
    project_id = fk("project", nullable=False)
    status = db.Column(S(20), nullable=False, default="active")
    role = db.Column(S(20), nullable=False, default="member")
    joined_at = db.Column(D(), nullable=False, default=now)
    left_at = db.Column(D())


class TaskParticipant(Entity, db.Model):
    __tablename__ = "task_participant"
    __table_args__ = (
        db.UniqueConstraint("task_id", "user_id"),
        db.Index(
            "uq_task_responsible",
            "task_id",
            unique=True,
            sqlite_where=text("role='responsible'"),
            postgresql_where=text("role='responsible'"),
        ),
    )
    task_id = fk("task", nullable=False)
    user_id = fk("user", nullable=False)
    role = db.Column(S(20), nullable=False)


class TaskCriterion(Entity, db.Model):
    __tablename__ = "task_criterion"
    __table_args__ = (db.UniqueConstraint("task_id", "criterion_id"),)
    task_id = fk("task", nullable=False)
    criterion_id = fk("criterion", nullable=False)


class GroupInvitation(Entity, db.Model):
    __tablename__ = "group_invitation"
    __table_args__ = (db.UniqueConstraint("project_id", "user_id"),)
    project_id = fk("project", nullable=False)
    user_id = fk("user", nullable=False)
    invited_by = fk("user", nullable=False)
    kind = db.Column(S(12), nullable=False)
    status = db.Column(S(20), nullable=False, default="pending")
    responded_at = db.Column(D())


class WorkComplaint(Entity, db.Model):
    __tablename__ = "work_complaint"
    task_id = fk("task", nullable=False)
    raised_by = fk("user", nullable=False)
    target_id = fk("user", nullable=False)
    reason = db.Column(T, nullable=False)
    explanation = db.Column(T)
    status = db.Column(S(20), nullable=False, default="open")
    handler = db.Column(S(20), nullable=False, default="leader")
    escalation_reason = db.Column(T)
    resolution = db.Column(T)
    resolved_by = fk("user")
    resolved_at = db.Column(D())


class AllocationChange(Entity, db.Model):
    __tablename__ = "allocation_change"
    __table_args__ = (db.UniqueConstraint("complaint_id"),)
    task_id = fk("task", nullable=False)
    complaint_id = fk("work_complaint", nullable=False)
    decided_by = fk("user", nullable=False)
    shares = db.Column(J, nullable=False)
    reason = db.Column(T, nullable=False)


class QualityEvaluation(Entity, db.Model):
    __tablename__ = "quality_evaluation"
    __table_args__ = (db.UniqueConstraint("project_id", "criterion_id"),)
    project_id = fk("project", nullable=False)
    criterion_id = fk("criterion", nullable=False)
    level_id = fk("criterion_level", nullable=False)
    rationale = db.Column(T, nullable=False)
    evaluated_by = fk("user", nullable=False)


class EvidenceAsset(Entity, db.Model):
    __tablename__ = "evidence_asset"
    task_id = fk("task", nullable=False)
    uploaded_by = fk("user", nullable=False)
    kind = db.Column(S(12), nullable=False)
    storage_key = db.Column(S(255))
    url = db.Column(T)
    original_filename = db.Column(S(255))
    mime_type = db.Column(S(120))
    size_bytes = db.Column(I, nullable=False, default=0)
    sha256 = db.Column(S(64))
    integrity_status = db.Column(S(40), nullable=False, default="fixed_file")
    legacy_attachment_id = fk("attachment")


class EvidenceRevision(Entity, db.Model):
    __tablename__ = "evidence_revision"
    __table_args__ = (db.UniqueConstraint("task_id", "revision_no"),)
    task_id = fk("task", nullable=False)
    revision_no = db.Column(I, nullable=False)
    description = db.Column(T, nullable=False)
    created_by = fk("user", nullable=False)


class EvidenceRevisionAsset(db.Model):
    __tablename__ = "evidence_revision_asset"
    revision_id = fk("evidence_revision", primary_key=True)
    asset_id = fk("evidence_asset", primary_key=True)


class TaskSubmission(Entity, db.Model):
    __tablename__ = "task_submission"
    __table_args__ = (
        db.UniqueConstraint("task_id", "attempt_no"),
        db.UniqueConstraint("revision_id"),
    )
    task_id = fk("task", nullable=False)
    revision_id = fk("evidence_revision", nullable=False)
    attempt_no = db.Column(I, nullable=False)
    submitted_by = fk("user", nullable=False)
    participant_ids = db.Column(J, nullable=False, default=list)
    received_at = db.Column(D(), nullable=False)
    submitted_due_at = db.Column(D(), nullable=False)
    status = db.Column(S(20), nullable=False, default="pending")
    reviewed_at = db.Column(D())
    reviewed_by = fk("user")
    review_reason = db.Column(T)


class ContributionClaim(Entity, db.Model):
    __tablename__ = "contribution_claim"
    __table_args__ = (db.UniqueConstraint("task_id", "user_id"),)
    task_id = fk("task", nullable=False)
    user_id = fk("user", nullable=False)
    summary = db.Column(T, nullable=False)
    status = db.Column(S(20), nullable=False, default="draft")
    revision = db.Column(I, nullable=False, default=0)
    evidence_refs = db.Column(J, nullable=False, default=list)
    submitted_at = db.Column(D())


class ClaimRevision(Entity, db.Model):
    __tablename__ = "claim_revision"
    __table_args__ = (db.UniqueConstraint("claim_id", "revision"),)
    claim_id = fk("contribution_claim", nullable=False)
    revision = db.Column(I, nullable=False)
    summary = db.Column(T, nullable=False)
    evidence_refs = db.Column(J, nullable=False)


class ContributionResponse(Entity, db.Model):
    __tablename__ = "contribution_response"
    __table_args__ = (db.UniqueConstraint("claim_revision_id", "responder_id"),)
    claim_revision_id = fk("claim_revision", nullable=False)
    responder_id = fk("user", nullable=False)
    verdict = db.Column(S(20), nullable=False)
    reason = db.Column(T, nullable=False, default="")


class DisputeDecision(Entity, db.Model):
    __tablename__ = "dispute_decision"
    claim_id = fk("contribution_claim", nullable=False)
    reviewer_id = fk("user", nullable=False)
    outcome = db.Column(S(30), nullable=False)
    rationale = db.Column(T, nullable=False)
    evidence_refs = db.Column(J, nullable=False)
    follow_up = db.Column(T)


class ChangeRequest(Entity, db.Model):
    __tablename__ = "change_request"
    project_id = fk("project", nullable=False)
    task_id = fk("task")
    kind = db.Column(S(30), nullable=False)
    before_json = db.Column(J, nullable=False)
    proposed_json = db.Column(J, nullable=False)
    reason = db.Column(T, nullable=False)
    status = db.Column(S(20), nullable=False, default="pending")
    requested_by = fk("user", nullable=False)
    decided_by = fk("user")
    decided_at = db.Column(D())
    decision_reason = db.Column(T)


class ProgressCheckin(Entity, db.Model):
    __tablename__ = "progress_checkin"
    task_id = fk("task", nullable=False)
    user_id = fk("user", nullable=False)
    content = db.Column(T, nullable=False)
    evidence_refs = db.Column(J, nullable=False, default=list)


class FinalSubmission(Entity, db.Model):
    __tablename__ = "final_submission"
    project_id = fk("project", nullable=False)
    revision_id = fk("evidence_revision", nullable=False)
    submitted_by = fk("user", nullable=False)
    required_milestone_ids = db.Column(J, nullable=False)


class RiskCase(Entity, db.Model):
    __tablename__ = "risk_case"
    __table_args__ = (
        db.Index(
            "uq_open_risk",
            "subject_key",
            "rule_code",
            unique=True,
            sqlite_where=text("status NOT IN ('resolved','dismissed')"),
            postgresql_where=text("status NOT IN ('resolved','dismissed')"),
        ),
        db.Index("ix_risk_queue", "owner_id", "status", "next_review_at"),
    )
    project_id = fk("project", nullable=False)
    task_id = fk("task")
    subject_key = db.Column(S(60), nullable=False)
    rule_code = db.Column(S(40), nullable=False)
    rule_version = db.Column(I, nullable=False, default=1)
    severity = db.Column(S(20), nullable=False)
    status = db.Column(S(30), nullable=False, default="new")
    owner_id = fk("user")
    opened_at = db.Column(D(), nullable=False)
    last_detected_at = db.Column(D(), nullable=False)
    next_review_at = db.Column(D())
    resolved_at = db.Column(D())
    reason_json = db.Column(J, nullable=False)
    episode_no = db.Column(I, nullable=False)
    escalated_at = db.Column(D())


class InterventionAction(Entity, db.Model):
    __tablename__ = "intervention_action"
    risk_case_id = fk("risk_case", nullable=False)
    actor_id = fk("user", nullable=False)
    action_type = db.Column(S(30), nullable=False)
    content = db.Column(T, nullable=False)
    due_at = db.Column(D())
    outcome = db.Column(T)
    completed_at = db.Column(D())


class PeerRound(Entity, db.Model):
    __tablename__ = "peer_round"
    assignment_id = fk("assignment", nullable=False)
    title = db.Column(S(200), nullable=False)
    opens_at = db.Column(D(), nullable=False)
    closes_at = db.Column(D(), nullable=False)
    status = db.Column(S(20), nullable=False, default="draft")
    visibility_policy = db.Column(
        S(100), nullable=False, default="instructor_identity_student_aggregate_min3"
    )
    criteria_json = db.Column(J, nullable=False)
    roster_json = db.Column(J, nullable=False, default=dict)


class PeerResponse(Entity, db.Model):
    __tablename__ = "peer_response"
    __table_args__ = (
        db.UniqueConstraint("round_id", "reviewer_id", "reviewee_id"),
        db.CheckConstraint("reviewer_id <> reviewee_id"),
    )
    round_id = fk("peer_round", nullable=False)
    reviewer_id = fk("user", nullable=False)
    reviewee_id = fk("user", nullable=False)
    project_id = fk("project", nullable=False)
    status = db.Column(S(20), nullable=False, default="draft")
    submitted_at = db.Column(D())
    items_json = db.Column(J, nullable=False)


class PeerResponseRevision(Entity, db.Model):
    __tablename__ = "peer_response_revision"
    response_id = fk("peer_response", nullable=False)
    items_json = db.Column(J, nullable=False)
    status = db.Column(S(20), nullable=False)


class AssessmentCycle(Entity, db.Model):
    __tablename__ = "assessment_cycle"
    __table_args__ = (db.UniqueConstraint("assignment_id", "revision"),)
    assignment_id = fk("assignment", nullable=False)
    revision = db.Column(I, nullable=False, default=1)
    status = db.Column(S(20), nullable=False, default="draft")
    appeal_closes_at = db.Column(D())
    published_at = db.Column(D())
    finalized_at = db.Column(D())


class AssessmentRecord(Entity, db.Model):
    __tablename__ = "assessment_record"
    __table_args__ = (
        db.UniqueConstraint("cycle_id", "student_id"),
        db.Index("ix_record_status", "cycle_id", "status"),
    )
    cycle_id = fk("assessment_cycle", nullable=False)
    student_id = fk("user", nullable=False)
    project_id = fk("project", nullable=False)
    policy_id = fk("assessment_policy", nullable=False)
    status = db.Column(S(20), nullable=False, default="incomplete")
    total_score = db.Column(db.Numeric(6, 2))
    assessor_id = fk("user")
    rationale = db.Column(T, default="")


class AssessmentItem(Entity, db.Model):
    __tablename__ = "assessment_item"
    __table_args__ = (
        db.UniqueConstraint("record_id", "criterion_id"),
        db.CheckConstraint("score IS NULL OR score >= 0"),
    )
    record_id = fk("assessment_record", nullable=False)
    criterion_id = fk("criterion", nullable=False)
    score = db.Column(db.Numeric(6, 2))
    rationale = db.Column(T, nullable=False)
    evidence_refs_json = db.Column(J, nullable=False)


class AssessmentSnapshot(Entity, db.Model):
    __tablename__ = "assessment_snapshot"
    __table_args__ = (db.UniqueConstraint("record_id", "snapshot_revision"),)
    record_id = fk("assessment_record", nullable=False)
    snapshot_revision = db.Column(I, nullable=False)
    payload_json = db.Column(J, nullable=False)
    sha256 = db.Column(S(64), nullable=False)
    created_by = fk("user", nullable=False)


class Appeal(Entity, db.Model):
    __tablename__ = "appeal"
    __table_args__ = (
        db.Index(
            "uq_open_appeal",
            "assessment_record_id",
            unique=True,
            sqlite_where=text("status IN ('draft','submitted','under_review')"),
            postgresql_where=text("status IN ('draft','submitted','under_review')"),
        ),
        db.Index("ix_appeal_queue", "assigned_to", "status"),
    )
    assessment_record_id = fk("assessment_record", nullable=False)
    student_id = fk("user", nullable=False)
    reason = db.Column(T, nullable=False)
    requested_change = db.Column(T, nullable=False)
    evidence_refs = db.Column(J, nullable=False, default=list)
    status = db.Column(S(20), nullable=False, default="draft")
    submitted_at = db.Column(D())
    assigned_to = fk("user")


class AppealEvidence(Entity, db.Model):
    __tablename__ = "appeal_evidence"
    appeal_id = fk("appeal", nullable=False)
    storage_key = db.Column(S(255), nullable=False)
    original_filename = db.Column(S(255), nullable=False)
    sha256 = db.Column(S(64), nullable=False)
    size_bytes = db.Column(I, nullable=False)
    description = db.Column(T, nullable=False)


class AppealDecision(Entity, db.Model):
    __tablename__ = "appeal_decision"
    appeal_id = fk("appeal", nullable=False, unique=True)
    reviewer_id = fk("user", nullable=False)
    outcome = db.Column(S(20), nullable=False)
    rationale = db.Column(T, nullable=False)
    previous_snapshot_id = fk("assessment_snapshot", nullable=False)
    new_snapshot_id = fk("assessment_snapshot", nullable=False)


class ExportBatch(Entity, db.Model):
    __tablename__ = "export_batch"
    course_id = fk("course_offering", nullable=False)
    cycle_id = fk("assessment_cycle", nullable=False)
    format = db.Column(S(20), nullable=False, default="csv")
    status = db.Column(S(20), nullable=False, default="created")
    created_by = fk("user", nullable=False)
    snapshot_manifest = db.Column(J, nullable=False)
    sha256 = db.Column(S(64), nullable=False)
    row_count = db.Column(I, nullable=False)
    content = db.Column(T, nullable=False)
    receipt = db.Column(T)


class AuditEvent(Entity, db.Model):
    __tablename__ = "audit_event"
    __table_args__ = (
        db.Index("ix_audit_entity", "entity_type", "entity_id", "created_at"),
    )
    actor_id = fk("user")
    action = db.Column(S(80), nullable=False)
    entity_type = db.Column(S(80), nullable=False)
    entity_id = db.Column(I, nullable=False)
    course_id = fk("course_offering")
    project_id = fk("project")
    request_id = db.Column(S(64), nullable=False)
    before_json = db.Column(J, nullable=False, default=dict)
    after_json = db.Column(J, nullable=False, default=dict)
    reason = db.Column(T)


class OutboxEvent(Entity, db.Model):
    __tablename__ = "outbox_event"
    __table_args__ = (db.Index("ix_outbox_pending", "processed_at", "next_attempt_at"),)
    event_type = db.Column(S(80), nullable=False)
    aggregate_id = db.Column(I, nullable=False)
    payload = db.Column(J, nullable=False)
    processed_at = db.Column(D())
    attempts = db.Column(I, nullable=False, default=0)
    next_attempt_at = db.Column(D())


class Notification(Entity, db.Model):
    __tablename__ = "notification"
    __table_args__ = (db.UniqueConstraint("recipient_id", "event_id"),)
    recipient_id = fk("user", nullable=False)
    event_id = fk("outbox_event", nullable=False)
    title = db.Column(S(200), nullable=False)
    body = db.Column(T, nullable=False)
    target_path = db.Column(S(255), nullable=False)
    read_at = db.Column(D())


class ImportBatch(Entity, db.Model):
    __tablename__ = "import_batch"
    file_hash = db.Column(S(64), nullable=False)
    course_id = fk("course_offering", nullable=False)
    status = db.Column(S(20), nullable=False, default="previewed")
    mapping = db.Column(J, nullable=False)
    counts = db.Column(J, nullable=False)
    created_by = fk("user", nullable=False)


class ImportRow(Entity, db.Model):
    __tablename__ = "import_row"
    batch_id = fk("import_batch", nullable=False)
    row_no = db.Column(I, nullable=False)
    normalized_json = db.Column(J, nullable=False)
    errors_json = db.Column(J, nullable=False)
    action = db.Column(S(30), nullable=False)
    committed_entity_id = db.Column(I)


class IdempotencyRecord(Entity, db.Model):
    __tablename__ = "idempotency_record"
    __table_args__ = (db.UniqueConstraint("actor_id", "route", "key"),)
    actor_id = fk("user", nullable=False)
    route = db.Column(S(255), nullable=False)
    key = db.Column(S(128), nullable=False)
    request_hash = db.Column(S(64), nullable=False)
    response_status = db.Column(I, nullable=False)
    response_body = db.Column(J, nullable=False)
    expires_at = db.Column(D(), nullable=False)


class IntegrationJob(Entity, db.Model):
    __tablename__ = "integration_job"
    provider = db.Column(S(80), nullable=False)
    direction = db.Column(S(20), nullable=False)
    external_key = db.Column(S(255))
    idempotency_key = db.Column(S(128), unique=True)
    status = db.Column(S(30), nullable=False, default="disabled")
    attempts = db.Column(I, nullable=False, default=0)
    error_code = db.Column(S(80))


# ORM guard complements migration-installed DB triggers, including bulk SQL protection.
for cls in (
    EvidenceAsset,
    EvidenceRevision,
    EvidenceRevisionAsset,
    ClaimRevision,
    PeerResponseRevision,
    AssessmentSnapshot,
    AppealDecision,
    DisputeDecision,
    AuditEvent,
    FinalSubmission,
    AllocationChange,
):

    def immutable(mapper, connection, target):
        raise ValueError("Immutable academic record")

    event.listen(cls, "before_update", immutable)
    event.listen(cls, "before_delete", immutable)


class HelpRequest(Entity, db.Model):
    __tablename__ = "help_request"
    project_id = fk("project", nullable=False)
    task_id = fk("task")
    requested_by = fk("user", nullable=False)
    assigned_to = fk("user")
    subject = db.Column(S(200), nullable=False)
    content = db.Column(T, nullable=False)
    status = db.Column(S(20), nullable=False, default="submitted")
    response = db.Column(T)
    resolved_at = db.Column(D())


@event.listens_for(TaskSubmission, "before_update")
def preserve_submission_roster(mapper, connection, target):
    from sqlalchemy import inspect

    if inspect(target).attrs.participant_ids.history.has_changes():
        raise ValueError("Submission roster is immutable")


class AssignmentFile(Entity, db.Model):
    __tablename__ = 'assignment_file'
    assignment_id = fk('assignment', nullable=False)
    uploaded_by = fk('user', nullable=False)
    storage_key = db.Column(S(32), nullable=False, unique=True)
    original_filename = db.Column(S(240), nullable=False)
    mime_type = db.Column(S(150), nullable=False)
    size_bytes = db.Column(I, nullable=False)
    sha256 = db.Column(S(64), nullable=False)
