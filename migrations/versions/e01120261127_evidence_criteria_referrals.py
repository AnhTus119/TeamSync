"""Evidence criteria, per-submission evidence links, instructor referrals, team name.

Additive only: existing projects, tasks and submissions are kept untouched.
"""
from alembic import op
import sqlalchemy as sa
revision='e01120261127'
down_revision='d12220261122'
branch_labels=None
depends_on=None

def upgrade():
    bind=op.get_bind()
    cols={c['name'] for c in sa.inspect(bind).get_columns('project')}
    if 'team_name' not in cols:
        with op.batch_alter_table('project') as b:
            b.add_column(sa.Column('team_name',sa.String(120),nullable=False,server_default=''))
    from app.models.workflow import EvidenceCriterion, SubmissionEvidence, SubmissionReferral
    for model in (EvidenceCriterion, SubmissionEvidence, SubmissionReferral):
        model.__table__.create(bind, checkfirst=True)

def downgrade():
    for name in ('submission_referral','submission_evidence','evidence_criterion'):
        op.drop_table(name)
    with op.batch_alter_table('project') as b:
        b.drop_column('team_name')
