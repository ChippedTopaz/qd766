"""Explicit collection capability; prepared only, not applied to production."""
from alembic import op
import sqlalchemy as sa

revision = "20261003_0011"
down_revision = "20261003_0010"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("account_collection_permissions",
        sa.Column("account_id", sa.Uuid(), sa.ForeignKey("user_accounts.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("granted_by", sa.Uuid(), sa.ForeignKey("user_accounts.id", ondelete="RESTRICT")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()))


def downgrade():
    op.drop_table("account_collection_permissions")
