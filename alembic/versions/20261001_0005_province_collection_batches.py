"""Add sequential national province collection batches.

Revision ID: 20261001_0005
Revises: 20260929_0004
Create Date: 2026-10-01
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20261001_0005"
down_revision = "20260929_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    json_type = postgresql.JSONB(astext_type=sa.Text())
    op.create_table(
        "province_collection_batches",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("idempotency_key", sa.String(length=240), nullable=False),
        sa.Column("state", sa.String(length=16), nullable=False),
        sa.Column("period_type", sa.String(length=16), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("period_value", sa.Integer(), nullable=True),
        sa.Column("catalog_version", sa.String(length=160), nullable=False),
        sa.Column("total_items", sa.Integer(), nullable=False),
        sa.Column("available_items", sa.Integer(), nullable=False),
        sa.Column("completed_items", sa.Integer(), nullable=False),
        sa.Column("failed_items", sa.Integer(), nullable=False),
        sa.Column("error", json_type, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "state IN ('queued', 'running', 'succeeded', 'failed', 'halted')",
            name="ck_province_collection_batch_state",
        ),
        sa.CheckConstraint(
            "period_type IN ('month', 'quarter', 'year')",
            name="ck_province_collection_batch_period",
        ),
        sa.CheckConstraint(
            "(period_type = 'month' AND period_value BETWEEN 1 AND 12) OR "
            "(period_type = 'quarter' AND period_value BETWEEN 1 AND 4) OR "
            "(period_type = 'year' AND period_value IS NULL)",
            name="ck_province_collection_batch_period_value",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("idempotency_key"),
    )
    op.create_index(
        "ix_province_collection_batch_state_created",
        "province_collection_batches",
        ["state", "created_at"],
    )

    op.create_table(
        "province_collection_batch_items",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("batch_id", sa.Uuid(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("province_code", sa.String(length=2), nullable=False),
        sa.Column("province_name", sa.Text(), nullable=False),
        sa.Column("root_department_id", sa.Uuid(), nullable=False),
        sa.Column("state", sa.String(length=16), nullable=False),
        sa.Column("job_id", sa.Uuid(), nullable=True),
        sa.Column("error", json_type, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "state IN ('pending', 'queued', 'running', 'succeeded', 'failed', 'halted', 'skipped')",
            name="ck_province_collection_batch_item_state",
        ),
        sa.ForeignKeyConstraint(["batch_id"], ["province_collection_batches.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["root_department_id"], ["departments.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["job_id"], ["collection_jobs.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("batch_id", "root_department_id", name="uq_province_batch_item_root"),
    )
    op.create_index("ix_province_collection_batch_items_batch_id", "province_collection_batch_items", ["batch_id"])
    op.create_index("ix_province_collection_batch_items_root_department_id", "province_collection_batch_items", ["root_department_id"])
    op.create_index("ix_province_collection_batch_items_job_id", "province_collection_batch_items", ["job_id"])
    op.create_index(
        "ix_province_batch_item_next",
        "province_collection_batch_items",
        ["batch_id", "state", "position"],
    )


def downgrade() -> None:
    op.drop_index("ix_province_batch_item_next", table_name="province_collection_batch_items")
    op.drop_index("ix_province_collection_batch_items_job_id", table_name="province_collection_batch_items")
    op.drop_index("ix_province_collection_batch_items_root_department_id", table_name="province_collection_batch_items")
    op.drop_index("ix_province_collection_batch_items_batch_id", table_name="province_collection_batch_items")
    op.drop_table("province_collection_batch_items")
    op.drop_index("ix_province_collection_batch_state_created", table_name="province_collection_batches")
    op.drop_table("province_collection_batches")
