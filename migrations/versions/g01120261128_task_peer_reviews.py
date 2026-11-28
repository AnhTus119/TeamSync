"""Per-task peer reviews replace evaluation rounds (additive; old round tables are kept)."""
from alembic import op
revision='g01120261128'
down_revision='f01120261127'
branch_labels=None
depends_on=None

def upgrade():
    from app.models.workflow import TaskPeerReview
    TaskPeerReview.__table__.create(op.get_bind(), checkfirst=True)

def downgrade():
    op.drop_table('task_peer_review')
