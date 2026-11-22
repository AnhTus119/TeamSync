"""Non-destructive assignment publication visibility."""
from alembic import op
import sqlalchemy as sa
revision='c61120261111'
down_revision='b51120261111'
branch_labels=None
depends_on=None

def upgrade():
    op.add_column('assignment',sa.Column('group_method',sa.String(20),nullable=False,server_default='random'))
    op.add_column('assignment',sa.Column('is_hidden',sa.Boolean(),nullable=False,server_default=sa.false()))
    op.execute("UPDATE assignment SET is_hidden = 1 WHERE status = 'draft'")

def downgrade():
    with op.batch_alter_table('assignment') as batch:
        batch.drop_column('is_hidden')
        batch.drop_column('group_method')
