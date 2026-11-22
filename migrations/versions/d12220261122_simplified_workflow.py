"""Group departures and durable report/delivery records."""
from alembic import op
import sqlalchemy as sa
revision='d12220261122'
down_revision='c61120261111'
branch_labels=None
depends_on=None

def upgrade():
    from app.models.workflow import GroupDeparture, ReportSnapshot, DeadlineReminder, GroupDelivery
    for model in (GroupDeparture, ReportSnapshot, DeadlineReminder, GroupDelivery):
        model.__table__.create(op.get_bind(), checkfirst=True)

def downgrade():
    for name in ('group_delivery','deadline_reminder','report_snapshot','group_departure'):
        op.drop_table(name)
