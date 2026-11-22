"""Preserve 1–5 history while supporting every point on the 1–10 matrix.

Revision ID: af10e20261110
Revises: 7361bfd76713
"""
from alembic import op
import sqlalchemy as sa

revision = 'af10e20261110'
down_revision = '7361bfd76713'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('matrix_review', sa.Column('attitude10', sa.Integer(), sa.CheckConstraint('attitude10 IS NULL OR attitude10 BETWEEN 1 AND 10'), nullable=True))
    op.add_column('matrix_review', sa.Column('quality10', sa.Integer(), sa.CheckConstraint('quality10 IS NULL OR quality10 BETWEEN 1 AND 10'), nullable=True))
    op.execute('UPDATE matrix_review SET attitude10 = attitude * 2, quality10 = quality * 2')


def downgrade():
    # Odd 10-point values would lose precision on the old 5-point scale.
    connection = op.get_bind()
    if connection.execute(sa.text('SELECT COUNT(*) FROM matrix_review WHERE attitude10 % 2 <> 0 OR quality10 % 2 <> 0')).scalar():
        raise RuntimeError('Downgrade would discard 10-point precision; export data first')
    op.execute('UPDATE matrix_review SET attitude = COALESCE(attitude10 / 2, attitude), quality = COALESCE(quality10 / 2, quality)')
    with op.batch_alter_table('matrix_review') as batch:
        batch.drop_column('quality10')
        batch.drop_column('attitude10')
