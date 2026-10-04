"""Explicit source-wallet opt-in; production activation is not enabled."""
from alembic import op
import sqlalchemy as sa
revision = "20261004_0015"
down_revision = "20261004_0014"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("credit_wallet_enrollments",
        sa.Column("account_id", sa.Uuid(), sa.ForeignKey("user_accounts.id", ondelete="RESTRICT"), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()))


def downgrade():
    if op.get_bind().execute(sa.text("SELECT count(*) FROM credit_wallet_enrollments")).scalar():
        raise RuntimeError("Wallet enrollments exist; use reviewed rollback")
    op.drop_table("credit_wallet_enrollments")
