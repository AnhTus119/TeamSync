"""Assignment formation policy and private supporting files."""
from alembic import op
import sqlalchemy as sa
revision='b51120261111'
down_revision='af10e20261110'
branch_labels=None
depends_on=None

def upgrade():
    op.add_column('assignment',sa.Column('group_mode',sa.String(16),nullable=False,server_default='self'))
    op.add_column('assignment',sa.Column('formation_due_at',sa.DateTime(timezone=True),nullable=True))
    op.create_table('assignment_file',
        sa.Column('id',sa.Integer(),primary_key=True),
        sa.Column('created_at',sa.DateTime(timezone=True),nullable=False),
        sa.Column('updated_at',sa.DateTime(timezone=True),nullable=False),
        sa.Column('version',sa.Integer(),nullable=False),
        sa.Column('assignment_id',sa.Integer(),sa.ForeignKey('assignment.id',ondelete='RESTRICT'),nullable=False),
        sa.Column('uploaded_by',sa.Integer(),sa.ForeignKey('user.id',ondelete='RESTRICT'),nullable=False),
        sa.Column('storage_key',sa.String(32),nullable=False,unique=True),
        sa.Column('original_filename',sa.String(240),nullable=False),
        sa.Column('mime_type',sa.String(150),nullable=False),
        sa.Column('size_bytes',sa.Integer(),nullable=False),
        sa.Column('sha256',sa.String(64),nullable=False))

def downgrade():
    op.drop_table('assignment_file')
    with op.batch_alter_table('assignment') as batch:
        batch.drop_column('formation_due_at')
        batch.drop_column('group_mode')
