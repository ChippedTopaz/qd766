"""Independent agency challenges; no account, Credit or source-data changes."""
from alembic import op
import sqlalchemy as sa
revision='20261011_0026'
down_revision='20261009_0025'
branch_labels=depends_on=None

def upgrade():
    op.create_table('agency_challenges',
        sa.Column('id',sa.Uuid(),primary_key=True),
        sa.Column('sender_id',sa.Uuid(),sa.ForeignKey('user_accounts.id',ondelete='RESTRICT'),nullable=False),
        sa.Column('recipient_id',sa.Uuid(),sa.ForeignKey('user_accounts.id',ondelete='RESTRICT'),nullable=False),
        sa.Column('root_department_id',sa.Uuid(),sa.ForeignKey('departments.id',ondelete='RESTRICT'),nullable=False),
        sa.Column('sender_unit_id',sa.Uuid(),sa.ForeignKey('departments.id',ondelete='RESTRICT'),nullable=False),
        sa.Column('recipient_unit_id',sa.Uuid(),sa.ForeignKey('departments.id',ondelete='RESTRICT'),nullable=False),
        sa.Column('pair_key',sa.String(80),nullable=False),
        sa.Column('period_type',sa.String(16),nullable=False),
        sa.Column('year',sa.Integer(),nullable=False),
        sa.Column('period_key',sa.Integer(),nullable=False),
        sa.Column('state',sa.String(16),nullable=False),
        sa.Column('sender_score',sa.Numeric(10,2)),
        sa.Column('recipient_score',sa.Numeric(10,2)),
        sa.Column('result_snapshot_id',sa.Uuid(),sa.ForeignKey('snapshots.id',ondelete='RESTRICT')),
        sa.Column('result_collection_job_id',sa.Uuid(),sa.ForeignKey('collection_jobs.id',ondelete='RESTRICT')),
        sa.Column('created_at',sa.DateTime(timezone=True),nullable=False,server_default=sa.func.now()),
        sa.Column('accepted_at',sa.DateTime(timezone=True)),
        sa.Column('finished_at',sa.DateTime(timezone=True)),
        sa.UniqueConstraint('pair_key','period_type','year','period_key',name='uq_challenge_pair_period'),
        sa.CheckConstraint("state IN ('pending','accepted','declined','finished')",name='ck_challenge_state'),
        sa.CheckConstraint("period_type IN ('month','quarter','year')",name='ck_challenge_period'),
        sa.CheckConstraint('sender_id != recipient_id',name='ck_challenge_distinct_accounts'))
    op.create_index('ix_agency_challenges_sender_id','agency_challenges',['sender_id'])
    op.create_index('ix_agency_challenges_recipient_id','agency_challenges',['recipient_id'])

def downgrade():
    raise RuntimeError('Preserve challenge history; restore a reviewed backup for schema rollback.')
