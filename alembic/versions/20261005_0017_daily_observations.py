"""Immutable daily report observations; no historical dates are synthesized."""
from alembic import op
import sqlalchemy as sa
revision = "20261005_0017"
down_revision = "20261005_0016"
branch_labels = depends_on = None

def upgrade():
    op.create_table('daily_observations',
        sa.Column('id',sa.Uuid(),primary_key=True),
        sa.Column('block_key',sa.String(160),nullable=False,unique=True),
        sa.Column('report_date',sa.Date(),nullable=False),
        sa.Column('root_department_id',sa.Uuid(),sa.ForeignKey('departments.id',ondelete='RESTRICT'),nullable=False),
        sa.Column('period_type',sa.String(16),nullable=False),
        sa.Column('year',sa.Integer(),nullable=False),sa.Column('period_value',sa.Integer()),
        sa.Column('snapshot_id',sa.Uuid(),sa.ForeignKey('snapshots.id',ondelete='RESTRICT'),nullable=False),
        sa.Column('national_summary_id',sa.Uuid(),sa.ForeignKey('national_summary_snapshots.id',ondelete='RESTRICT'),nullable=False),
        sa.Column('captured_at',sa.DateTime(timezone=True),nullable=False))
    op.create_index('ix_daily_observations_report_date','daily_observations',['report_date'])
    op.create_index('ix_daily_observations_root_department_id','daily_observations',['root_department_id'])
    op.create_index('ix_daily_lookup','daily_observations',['root_department_id','period_type','year','period_value','report_date'])

def downgrade():
    raise RuntimeError('Daily history must be backed up and reviewed before removal')
