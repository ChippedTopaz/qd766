"""Isolated subscription cycle core; not activated on production."""
from alembic import op
import sqlalchemy as sa

revision = "20261004_0014"
down_revision = "20261004_0013"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("subscription_cycles",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("account_id", sa.Uuid(), sa.ForeignKey("user_accounts.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("operation_key", sa.String(200), nullable=False),
        sa.Column("tier", sa.String(16), nullable=False),
        sa.Column("origin", sa.String(16), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("included_credit", sa.Integer(), nullable=False),
        sa.Column("granted_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("account_id", "operation_key", name="uq_subscription_cycle_operation"),
        sa.CheckConstraint("tier IN ('agency', 'province')", name="ck_subscription_cycle_tier"),
        sa.CheckConstraint("origin IN ('trial', 'paid', 'redemption')", name="ck_subscription_cycle_origin"),
        sa.CheckConstraint("ends_at > starts_at", name="ck_subscription_cycle_dates"),
        sa.CheckConstraint("included_credit >= 0", name="ck_subscription_cycle_credit"))
    op.create_index("ix_subscription_cycle_account", "subscription_cycles", ["account_id", "starts_at"])


def downgrade():
    if op.get_bind().execute(sa.text("SELECT count(*) FROM subscription_cycles")).scalar():
        raise RuntimeError("Subscription history exists; use a reviewed rollback plan")
    op.drop_table("subscription_cycles")
