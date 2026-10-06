"""Durable analysis queue; no admission or Credit backfill."""
from alembic import op
import sqlalchemy as sa

revision = '20261007_0019'
down_revision = '20261006_0018'
branch_labels = depends_on = None


def upgrade():
    op.drop_constraint('ck_gemini_analysis_state','gemini_analyses',type_='check')
    op.create_check_constraint('ck_gemini_analysis_state','gemini_analyses',
        "state IN ('queued', 'running', 'ready', 'failed', 'cancelled')")
    op.create_index('ix_gemini_analysis_queue','gemini_analyses',['state','created_at','id'])
    op.create_table('analysis_queue_entries',
        sa.Column('analysis_id',sa.Uuid(),sa.ForeignKey('gemini_analyses.id',ondelete='RESTRICT'),primary_key=True),
        sa.Column('expires_at',sa.DateTime(timezone=True),nullable=False),
        sa.Column('started_at',sa.DateTime(timezone=True)),
        sa.Column('lease_until',sa.DateTime(timezone=True)),
        sa.Column('worker_token',sa.Uuid()))


def downgrade():
    raise RuntimeError('Review pending holds and preserve analysis history before rollback')
