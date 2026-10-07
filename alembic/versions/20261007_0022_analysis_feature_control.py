"""Add independent AI maintenance switch; preserve jobs, wallet and prompt history."""
from alembic import op
import sqlalchemy as sa
revision='20261007_0022'
down_revision='20261007_0021'
branch_labels=depends_on=None

def upgrade():
    op.create_table('analysis_feature_control',
        sa.Column('id',sa.Integer(),primary_key=True,autoincrement=False),
        sa.Column('enabled',sa.Boolean(),nullable=False),
        sa.Column('revision',sa.Integer(),nullable=False),
        sa.Column('actor_id',sa.Uuid(),sa.ForeignKey('user_accounts.id',ondelete='RESTRICT'),nullable=False),
        sa.Column('updated_at',sa.DateTime(timezone=True),nullable=False),
        sa.CheckConstraint('id = 1 AND revision > 0',name='ck_analysis_feature_singleton'))

def downgrade():
    raise RuntimeError('Preserve maintenance switch; review before rollback')
