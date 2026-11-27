"""Personal/shared timeline entries (additive)."""
from alembic import op
revision='f01120261127'
down_revision='e01120261127'
branch_labels=None
depends_on=None

def upgrade():
    from app.models.workflow import ScheduleItem
    ScheduleItem.__table__.create(op.get_bind(), checkfirst=True)

def downgrade():
    op.drop_table('schedule_item')
