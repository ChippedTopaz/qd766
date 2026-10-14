"""Separate source-monitor drafts/alerts; never rewrite published snapshots."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
revision='20261014_0028'
down_revision='20261011_0027'
branch_labels=depends_on=None

def upgrade():
    doc=sa.JSON().with_variant(JSONB(),'postgresql')
    op.create_table('source_monitor_baselines',sa.Column('key',sa.String(240),primary_key=True),
        sa.Column('profile',doc,nullable=False),sa.Column('fingerprint',sa.String(64),nullable=False),
        sa.Column('updated_at',sa.DateTime(timezone=True),nullable=False,server_default=sa.func.now()))
    op.create_table('source_monitor_samples',sa.Column('key',sa.String(40),primary_key=True),
        sa.Column('year',sa.Integer(),nullable=False),sa.Column('month',sa.Integer(),nullable=False),
        sa.Column('baseline_id',sa.Uuid(),sa.ForeignKey('national_summary_snapshots.id',ondelete='RESTRICT'),nullable=False),
        sa.Column('fingerprint',sa.String(64),nullable=False),sa.Column('payload',doc,nullable=False),
        sa.Column('checked_at',sa.DateTime(timezone=True),nullable=False))
    op.create_table('source_monitor_alerts',sa.Column('id',sa.Uuid(),primary_key=True),
        sa.Column('dedupe_key',sa.String(64),nullable=False,unique=True),sa.Column('kind',sa.String(24),nullable=False),
        sa.Column('title',sa.String(240),nullable=False),sa.Column('details',doc,nullable=False),
        sa.Column('occurrences',sa.Integer(),nullable=False),
        sa.Column('created_at',sa.DateTime(timezone=True),nullable=False,server_default=sa.func.now()),
        sa.Column('updated_at',sa.DateTime(timezone=True),nullable=False,server_default=sa.func.now()),
        sa.Column('read_at',sa.DateTime(timezone=True)),sa.Column('resolved_at',sa.DateTime(timezone=True)),
        sa.Column('reviewed_by',sa.Uuid(),sa.ForeignKey('user_accounts.id',ondelete='RESTRICT')))
    op.create_index('ix_source_alert_state_time','source_monitor_alerts',['resolved_at','created_at'])
    op.create_table('source_monitor_runs',sa.Column('day',sa.Date(),primary_key=True),
        sa.Column('state',sa.String(24),nullable=False),sa.Column('details',doc,nullable=False),
        sa.Column('updated_at',sa.DateTime(timezone=True),nullable=False))

def downgrade():
    raise RuntimeError('Preserve monitor evidence; disable the task/feature rather than deleting history.')
