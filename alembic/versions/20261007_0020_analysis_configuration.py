"""Admin-managed, append-only analysis guidance and knowledge."""
from alembic import op
import sqlalchemy as sa
revision='20261007_0020'
down_revision='20261007_0019'
branch_labels=depends_on=None

def upgrade():
    op.create_table('analysis_config_revisions',
        sa.Column('version',sa.Integer(),primary_key=True,autoincrement=False),
        sa.Column('guidance',sa.Text(),nullable=False),sa.Column('knowledge',sa.Text(),nullable=False),
        sa.Column('note',sa.String(500),nullable=False),
        sa.Column('actor_id',sa.Uuid(),sa.ForeignKey('user_accounts.id',ondelete='RESTRICT'),nullable=False),
        sa.Column('created_at',sa.DateTime(timezone=True),nullable=False),
        sa.CheckConstraint('version > 0',name='ck_analysis_config_version'))
    op.create_table('analysis_config_head',sa.Column('id',sa.Integer(),primary_key=True,autoincrement=False),
        sa.Column('version',sa.Integer(),sa.ForeignKey('analysis_config_revisions.version',ondelete='RESTRICT'),nullable=False),
        sa.CheckConstraint('id = 1',name='ck_analysis_config_singleton'))

def downgrade():
    raise RuntimeError('Preserve approved knowledge and audit history; review before rollback')
