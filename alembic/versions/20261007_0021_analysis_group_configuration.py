"""Add group-scoped revisions; preserve all existing configuration and jobs."""
from alembic import op
import sqlalchemy as sa
revision='20261007_0021'
down_revision='20261007_0020'
branch_labels=depends_on=None

def upgrade():
    op.create_table('analysis_group_config_revisions',
        sa.Column('version',sa.Integer(),sa.ForeignKey('analysis_config_revisions.version',ondelete='RESTRICT'),primary_key=True),
        sa.Column('group_id',sa.String(64),primary_key=True),
        sa.Column('guidance',sa.Text(),nullable=False),
        sa.Column('knowledge',sa.Text(),nullable=False))

def downgrade():
    raise RuntimeError('Preserve approved group configuration history; review before rollback')
