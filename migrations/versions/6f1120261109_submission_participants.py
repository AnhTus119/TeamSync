"""Record the assigned team at submission time.

Revision ID: 6f1120261109
Revises: 5d8cdbe415c1
"""

import json
from alembic import op
import sqlalchemy as sa

revision = "6f1120261109"
down_revision = "5d8cdbe415c1"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("task_submission") as batch:
        batch.add_column(
            sa.Column("participant_ids", sa.JSON(), nullable=False, server_default="[]")
        )
    # Older submissions do not record their historical roster. Preserve the
    # known submitter rather than infer credit from today's assignments.
    connection = op.get_bind()
    for ident, submitter in connection.execute(
        sa.text("SELECT id, submitted_by FROM task_submission")
    ):
        connection.execute(
            sa.text("UPDATE task_submission SET participant_ids = :ids WHERE id = :id"),
            {"ids": json.dumps([submitter]), "id": ident},
        )


def downgrade():
    with op.batch_alter_table("task_submission") as batch:
        batch.drop_column("participant_ids")
