"""System notices and per-account per-publication popup preference."""
from alembic import op
import sqlalchemy as sa

revision = '20261016_0029'
down_revision = '20261014_0028'
branch_labels = depends_on = None


def upgrade():
    op.create_table('system_notices',
        sa.Column('id', sa.Uuid(), primary_key=True), sa.Column('title', sa.String(200), nullable=False),
        sa.Column('summary', sa.String(300), nullable=False), sa.Column('body', sa.Text(), nullable=False),
        sa.Column('kind', sa.String(20), nullable=False), sa.Column('state', sa.String(16), nullable=False),
        sa.Column('revision', sa.Integer(), nullable=False), sa.Column('publication', sa.Integer(), nullable=False),
        sa.Column('created_by', sa.Uuid(), sa.ForeignKey('user_accounts.id', ondelete='RESTRICT'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('published_at', sa.DateTime(timezone=True)),
        sa.CheckConstraint("state IN ('draft','published','archived')", name='ck_notice_state'),
        sa.CheckConstraint("kind IN ('info','important','maintenance')", name='ck_notice_kind'))
    op.create_index('ix_notice_published', 'system_notices', ['state', 'published_at'])
    op.create_table('system_notice_dismissals',
        sa.Column('account_id', sa.Uuid(), sa.ForeignKey('user_accounts.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('notice_id', sa.Uuid(), sa.ForeignKey('system_notices.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('publication', sa.Integer(), primary_key=True),
        sa.Column('dismissed_at', sa.DateTime(timezone=True), nullable=False))


def downgrade():
    op.drop_table('system_notice_dismissals')
    op.drop_index('ix_notice_published', table_name='system_notices')
    op.drop_table('system_notices')
