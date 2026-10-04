"""Source-aware Credit wallet core. Prepared, not applied to production."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
revision="20261004_0013"
down_revision="20261003_0012"
branch_labels=None
depends_on=None
document=sa.JSON().with_variant(postgresql.JSONB(),"postgresql")

def upgrade():
    op.create_table("credit_lots",
        sa.Column("id",sa.Uuid(),primary_key=True),
        sa.Column("account_id",sa.Uuid(),sa.ForeignKey("user_accounts.id",ondelete="RESTRICT"),nullable=False),
        sa.Column("source",sa.String(16),nullable=False),
        sa.Column("available",sa.Integer(),nullable=False),
        sa.Column("reserved",sa.Integer(),nullable=False),
        sa.Column("expires_at",sa.DateTime(timezone=True)),
        sa.Column("created_at",sa.DateTime(timezone=True),nullable=False,server_default=sa.func.now()),
        sa.CheckConstraint("source IN ('subscription', 'purchased')",name="ck_credit_lot_source"),
        sa.CheckConstraint("available >= 0 AND reserved >= 0",name="ck_credit_lot_balance"),
        sa.CheckConstraint("(source = 'purchased' AND expires_at IS NULL) OR (source = 'subscription' AND expires_at IS NOT NULL)",name="ck_credit_lot_expiration"))
    op.create_index("ix_credit_lot_account","credit_lots",["account_id"])
    op.create_table("credit_holds",
        sa.Column("id",sa.Uuid(),primary_key=True),
        sa.Column("account_id",sa.Uuid(),sa.ForeignKey("user_accounts.id",ondelete="RESTRICT"),nullable=False),
        sa.Column("request_key",sa.String(240),nullable=False),
        sa.Column("state",sa.String(16),nullable=False),
        sa.Column("amount",sa.Integer(),nullable=False),
        sa.Column("allocations",document,nullable=False),
        sa.Column("created_at",sa.DateTime(timezone=True),nullable=False,server_default=sa.func.now()),
        sa.UniqueConstraint("account_id","request_key",name="uq_credit_hold_request"),
        sa.CheckConstraint("state IN ('reserved', 'charged', 'refunded')",name="ck_credit_hold_state"),
        sa.CheckConstraint("amount > 0",name="ck_credit_hold_amount"))
    op.create_table("credit_wallet_events",
        sa.Column("id",sa.Uuid(),primary_key=True),
        sa.Column("account_id",sa.Uuid(),sa.ForeignKey("user_accounts.id",ondelete="RESTRICT"),nullable=False),
        sa.Column("event_key",sa.String(250),nullable=False),
        sa.Column("kind",sa.String(16),nullable=False),
        sa.Column("amount",sa.Integer(),nullable=False),
        sa.Column("details",document,nullable=False),
        sa.Column("created_at",sa.DateTime(timezone=True),nullable=False,server_default=sa.func.now()),
        sa.UniqueConstraint("account_id","event_key",name="uq_credit_wallet_event"),
        sa.CheckConstraint("kind IN ('grant', 'reserve', 'charge', 'refund', 'expire')",name="ck_credit_wallet_event_kind"),
        sa.CheckConstraint("amount > 0",name="ck_credit_wallet_event_amount"))
    op.create_index("ix_credit_wallet_event_account","credit_wallet_events",["account_id","created_at"])

def downgrade():
    # Never silently destroy financial history.
    for table in ("credit_wallet_events","credit_holds","credit_lots"):
        if op.get_bind().execute(sa.text(f"SELECT count(*) FROM {table}")).scalar():
            raise RuntimeError("Source-aware wallet contains financial data; use reviewed rollback plan")
    for table in ("credit_wallet_events","credit_holds","credit_lots"):op.drop_table(table)
