"""Editable formula reference with an unchanged, persisted original revision."""
from alembic import op
import sqlalchemy as sa
from datetime import datetime, timezone
revision='20261008_0024'
down_revision='20261007_0023'
branch_labels=depends_on=None

def upgrade():
    revisions=op.create_table('formula_config_revisions',
        sa.Column('version',sa.Integer(),primary_key=True,autoincrement=False),
        sa.Column('content',sa.JSON(),nullable=False),sa.Column('note',sa.String(500),nullable=False),
        sa.Column('actor_id',sa.Uuid(),sa.ForeignKey('user_accounts.id',ondelete='RESTRICT'),nullable=True),
        sa.Column('created_at',sa.DateTime(timezone=True),nullable=False))
    head=op.create_table('formula_config_head',sa.Column('id',sa.Integer(),primary_key=True,autoincrement=False),
        sa.Column('version',sa.Integer(),sa.ForeignKey('formula_config_revisions.version',ondelete='RESTRICT'),nullable=False),
        sa.CheckConstraint('id = 1',name='ck_formula_config_singleton'))
    from qd766.backend.formula_configuration import SEED
    op.bulk_insert(revisions,[dict(version=1,content=SEED,note='Nguyên trạng công thức trước khi bật quản lý nội dung',actor_id=None,created_at=datetime.now(timezone.utc))])
    op.bulk_insert(head,[dict(id=1,version=1)])

def downgrade():
    raise RuntimeError('Preserve formula content and revision history; review before rollback')
