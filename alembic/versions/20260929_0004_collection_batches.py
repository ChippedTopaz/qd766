"""Add sequential formality collection batches.

Revision ID: 20260929_0004
Revises: 20260928_0003
Create Date: 2026-09-29
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260929_0004"
down_revision = "20260928_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    json_type = postgresql.JSONB(astext_type=sa.Text())
    op.create_table(
        "collection_batches",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("idempotency_key", sa.String(length=240), nullable=False),
        sa.Column("state", sa.String(length=16), nullable=False),
        sa.Column("province_code", sa.String(length=2), nullable=False),
        sa.Column("root_department_id", sa.Uuid(), nullable=False),
        sa.Column("period_type", sa.String(length=16), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("period_value", sa.Integer(), nullable=True),
        sa.Column("filters", json_type, nullable=False),
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
            name="ck_collection_batch_state",
        ),
        sa.ForeignKeyConstraint(["root_department_id"], ["departments.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("idempotency_key"),
    )
    op.create_index("ix_collection_batches_root_department_id", "collection_batches", ["root_department_id"])
    op.create_index("ix_collection_batch_state_created", "collection_batches", ["state", "created_at"])

    op.create_table(
        "collection_batch_items",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("batch_id", sa.Uuid(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("formality_id", sa.Uuid(), nullable=False),
        sa.Column("formality_code", sa.String(length=80), nullable=False),
        sa.Column("formality_name", sa.Text(), nullable=False),
        sa.Column("state", sa.String(length=16), nullable=False),
        sa.Column("job_id", sa.Uuid(), nullable=True),
        sa.Column("error", json_type, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "state IN ('pending', 'queued', 'running', 'succeeded', 'failed', 'halted', 'skipped')",
            name="ck_collection_batch_item_state",
        ),
        sa.ForeignKeyConstraint(["batch_id"], ["collection_batches.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["job_id"], ["collection_jobs.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("batch_id", "formality_id", name="uq_batch_item_formality"),
    )
    op.create_index("ix_collection_batch_items_batch_id", "collection_batch_items", ["batch_id"])
    op.create_index("ix_collection_batch_items_job_id", "collection_batch_items", ["job_id"])
    op.create_index("ix_batch_item_next", "collection_batch_items", ["batch_id", "state", "position"])


def downgrade() -> None:
    op.drop_index("ix_batch_item_next", table_name="collection_batch_items")
    op.drop_index("ix_collection_batch_items_job_id", table_name="collection_batch_items")
    op.drop_index("ix_collection_batch_items_batch_id", table_name="collection_batch_items")
    op.drop_table("collection_batch_items")
    op.drop_index("ix_collection_batch_state_created", table_name="collection_batches")
    op.drop_index("ix_collection_batches_root_department_id", table_name="collection_batches")
    op.drop_table("collection_batches")
