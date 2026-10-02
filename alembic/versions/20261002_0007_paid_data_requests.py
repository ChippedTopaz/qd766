"""Add paid data requests, credit ledger and notifications.

Revision ID: 20261002_0007
Revises: 20261001_0006
Create Date: 2026-10-02
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20261002_0007"
down_revision = "20261001_0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    json_type = postgresql.JSONB(astext_type=sa.Text())
    op.create_table(
        "user_accounts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("external_subject", sa.String(length=240), nullable=False),
        sa.Column("display_name", sa.Text(), nullable=False),
        sa.Column("plan", sa.String(length=16), nullable=False),
        sa.Column("credit_balance", sa.Integer(), nullable=False),
        sa.Column("credit_reserved", sa.Integer(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("plan IN ('free', 'paid', 'admin')", name="ck_user_account_plan"),
        sa.CheckConstraint("credit_balance >= 0", name="ck_user_credit_balance"),
        sa.CheckConstraint("credit_reserved >= 0", name="ck_user_credit_reserved"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("external_subject"),
    )
    op.create_table(
        "paid_data_requests",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("account_id", sa.Uuid(), nullable=False),
        sa.Column("idempotency_key", sa.String(length=240), nullable=False),
        sa.Column("dataset_key", sa.String(length=240), nullable=False),
        sa.Column("state", sa.String(length=16), nullable=False),
        sa.Column("credit_cost", sa.Integer(), nullable=False),
        sa.Column("province_code", sa.String(length=2), nullable=False),
        sa.Column("root_department_id", sa.Uuid(), nullable=False),
        sa.Column("formality_id", sa.Uuid(), nullable=False),
        sa.Column("period_type", sa.String(length=16), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("period_value", sa.Integer(), nullable=True),
        sa.Column("collection_job_id", sa.Uuid(), nullable=True),
        sa.Column("snapshot_id", sa.Uuid(), nullable=True),
        sa.Column("error", json_type, nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "state IN ('reserved', 'waiting', 'ready', 'refunded')",
            name="ck_paid_data_request_state",
        ),
        sa.CheckConstraint("credit_cost > 0", name="ck_paid_data_request_credit_cost"),
        sa.ForeignKeyConstraint(["account_id"], ["user_accounts.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["collection_job_id"], ["collection_jobs.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["formality_id"], ["formalities.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["root_department_id"], ["departments.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["snapshot_id"], ["snapshots.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("idempotency_key"),
    )
    op.create_index("ix_paid_data_requests_account_id", "paid_data_requests", ["account_id"])
    op.create_index("ix_paid_data_requests_collection_job_id", "paid_data_requests", ["collection_job_id"])
    op.create_index("ix_paid_data_requests_dataset_key", "paid_data_requests", ["dataset_key"])
    op.create_index("ix_paid_data_requests_formality_id", "paid_data_requests", ["formality_id"])
    op.create_index("ix_paid_data_requests_root_department_id", "paid_data_requests", ["root_department_id"])
    op.create_index("ix_paid_data_requests_snapshot_id", "paid_data_requests", ["snapshot_id"])
    op.create_index("ix_paid_request_account_dataset", "paid_data_requests", ["account_id", "dataset_key"])
    op.create_index(
        "uq_paid_request_active_entitlement",
        "paid_data_requests",
        ["account_id", "dataset_key"],
        unique=True,
        postgresql_where=sa.text("state IN ('reserved', 'waiting', 'ready')"),
    )
    op.create_index("ix_paid_request_job_state", "paid_data_requests", ["collection_job_id", "state"])

    op.create_table(
        "credit_ledger_entries",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("event_key", sa.String(length=240), nullable=False),
        sa.Column("account_id", sa.Uuid(), nullable=False),
        sa.Column("paid_request_id", sa.Uuid(), nullable=True),
        sa.Column("entry_type", sa.String(length=16), nullable=False),
        sa.Column("amount", sa.Integer(), nullable=False),
        sa.Column("available_delta", sa.Integer(), nullable=False),
        sa.Column("reserved_delta", sa.Integer(), nullable=False),
        sa.Column("available_after", sa.Integer(), nullable=False),
        sa.Column("reserved_after", sa.Integer(), nullable=False),
        sa.Column("details", json_type, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "entry_type IN ('topup', 'reserve', 'charge', 'release', 'adjustment')",
            name="ck_credit_ledger_entry_type",
        ),
        sa.CheckConstraint("amount > 0", name="ck_credit_ledger_amount"),
        sa.ForeignKeyConstraint(["account_id"], ["user_accounts.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["paid_request_id"], ["paid_data_requests.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("event_key"),
    )
    op.create_index("ix_credit_ledger_entries_account_id", "credit_ledger_entries", ["account_id"])
    op.create_index("ix_credit_ledger_entries_paid_request_id", "credit_ledger_entries", ["paid_request_id"])
    op.create_index("ix_credit_ledger_account_created", "credit_ledger_entries", ["account_id", "created_at"])

    op.create_table(
        "user_notifications",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("account_id", sa.Uuid(), nullable=False),
        sa.Column("paid_request_id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.String(length=24), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("kind IN ('data-ready', 'data-failed')", name="ck_user_notification_kind"),
        sa.ForeignKeyConstraint(["account_id"], ["user_accounts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["paid_request_id"], ["paid_data_requests.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("paid_request_id", "kind", name="uq_notification_request_kind"),
    )
    op.create_index("ix_user_notifications_account_id", "user_notifications", ["account_id"])
    op.create_index("ix_user_notifications_paid_request_id", "user_notifications", ["paid_request_id"])
    op.create_index("ix_notification_account_read", "user_notifications", ["account_id", "read_at", "created_at"])


def downgrade() -> None:
    op.drop_table("user_notifications")
    op.drop_table("credit_ledger_entries")
    op.drop_table("paid_data_requests")
    op.drop_table("user_accounts")
