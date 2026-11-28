"""Mark timeline entries created by AI sắp lịch so a later run can re-arrange them (additive)."""
import sqlalchemy as sa
from alembic import op
revision='h01120261128'
down_revision='g01120261128'
branch_labels=None
depends_on=None

def upgrade():
    cols = {c['name'] for c in sa.inspect(op.get_bind()).get_columns('schedule_item')}
    if 'source' not in cols:
        op.add_column('schedule_item', sa.Column('source', sa.String(10), nullable=False, server_default=''))

def downgrade():
    with op.batch_alter_table('schedule_item') as b:
        b.drop_column('source')
