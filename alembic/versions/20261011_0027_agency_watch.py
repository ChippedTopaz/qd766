"""Store watched agencies per authenticated account, across devices."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
revision='20261011_0027'
down_revision='20261011_0026'
branch_labels=depends_on=None
def upgrade():
    op.create_index('ix_challenge_incoming','agency_challenges',['recipient_id','state','year'])
    op.create_index('ix_challenge_board','agency_challenges',['root_department_id','state','created_at'])
    op.create_table('agency_watch_preferences',
        sa.Column('account_id',sa.Uuid(),sa.ForeignKey('user_accounts.id',ondelete='RESTRICT'),primary_key=True),
        sa.Column('root_department_id',sa.Uuid(),sa.ForeignKey('departments.id',ondelete='RESTRICT'),primary_key=True),
        sa.Column('unit_ids',sa.JSON().with_variant(JSONB(),'postgresql'),nullable=False),
        sa.Column('updated_at',sa.DateTime(timezone=True),nullable=False,server_default=sa.func.now()))
def downgrade():
    raise RuntimeError('Preserve account preferences; restore a reviewed backup for rollback.')
