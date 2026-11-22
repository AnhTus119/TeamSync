"""Student groups, contribution complaints and product quality.

Revision ID: 7a1120261109
Revises: 6f1120261109
"""

from alembic import op
import sqlalchemy as sa

revision = "7a1120261109"
down_revision = "6f1120261109"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "group_invitation",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column(
            "project_id",
            sa.Integer(),
            sa.ForeignKey("project.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("user.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "invited_by",
            sa.Integer(),
            sa.ForeignKey("user.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("kind", sa.String(12), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("responded_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("project_id", "user_id"),
    )
    op.create_table(
        "work_complaint",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column(
            "task_id",
            sa.Integer(),
            sa.ForeignKey("task.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "raised_by",
            sa.Integer(),
            sa.ForeignKey("user.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "target_id",
            sa.Integer(),
            sa.ForeignKey("user.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "resolved_by",
            sa.Integer(),
            sa.ForeignKey("user.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("explanation", sa.Text()),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("handler", sa.String(20), nullable=False),
        sa.Column("escalation_reason", sa.Text()),
        sa.Column("resolution", sa.Text()),
        sa.Column("resolved_at", sa.DateTime(timezone=True)),
    )
    op.create_table(
        "allocation_change",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column(
            "task_id",
            sa.Integer(),
            sa.ForeignKey("task.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "complaint_id",
            sa.Integer(),
            sa.ForeignKey("work_complaint.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "decided_by",
            sa.Integer(),
            sa.ForeignKey("user.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("shares", sa.JSON(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.UniqueConstraint("complaint_id"),
    )
    op.create_table(
        "quality_evaluation",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column(
            "project_id",
            sa.Integer(),
            sa.ForeignKey("project.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "criterion_id",
            sa.Integer(),
            sa.ForeignKey("criterion.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "level_id",
            sa.Integer(),
            sa.ForeignKey("criterion_level.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "evaluated_by",
            sa.Integer(),
            sa.ForeignKey("user.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.UniqueConstraint("project_id", "criterion_id"),
    )
    # Preserve mentor relationships for existing groups after migration.
    op.execute(
        sa.text(
            """INSERT INTO group_invitation
        (project_id,user_id,invited_by,kind,status,responded_at,created_at,updated_at,version)
        SELECT p.id,e.user_id,p.created_by,'mentor','accepted',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP,1
        FROM project p JOIN assignment a ON a.id=p.assignment_id
        JOIN course_enrollment e ON e.course_id=a.course_id
        WHERE p.mode='academic' AND e.role='instructor' AND e.status='active'"""
        )
    )
    # The dependency workflow was explicitly removed; preserve ordinary projects.
    op.execute(
        sa.text(
            "DELETE FROM task_dependency WHERE task_id IN (SELECT task.id FROM task JOIN project ON task.project_id=project.id WHERE project.mode='academic')"
        )
    )
    if op.get_bind().dialect.name == "sqlite":
        op.execute(
            "CREATE TRIGGER submission_roster_immutable BEFORE UPDATE OF participant_ids ON task_submission WHEN NEW.participant_ids != OLD.participant_ids BEGIN SELECT RAISE(ABORT, 'Submission roster is immutable'); END"
        )
        for action in ("UPDATE", "DELETE"):
            op.execute(
                f"CREATE TRIGGER allocation_change_no_{action.lower()} BEFORE {action} ON allocation_change BEGIN SELECT RAISE(ABORT, 'Contribution decision is immutable'); END"
            )


def downgrade():
    if op.get_bind().dialect.name == "sqlite":
        for name in (
            "submission_roster_immutable",
            "allocation_change_no_update",
            "allocation_change_no_delete",
        ):
            op.execute(f"DROP TRIGGER IF EXISTS {name}")
    op.drop_table("quality_evaluation")
    op.drop_table("allocation_change")
    op.drop_table("work_complaint")
    op.drop_table("group_invitation")
