"""Create the QD766 backend schema.

Revision ID: 20260928_0001
Revises:
Create Date: 2026-09-28
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260928_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    json_type = postgresql.JSONB(astext_type=sa.Text())
    op.create_table(
        "departments",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(length=64), nullable=True),
        sa.Column("name", sa.Text(), nullable=True),
        sa.Column("department_type", sa.String(length=64), nullable=True),
        sa.Column("department_level", sa.String(length=64), nullable=True),
        sa.Column("agency_level", sa.String(length=64), nullable=True),
        sa.Column("attributes", json_type, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_departments_code", "departments", ["code"])

    op.create_table(
        "formalities",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(length=80), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("state", sa.String(length=40), nullable=True),
        sa.Column("owning_department_id", sa.Uuid(), nullable=True),
        sa.Column("attributes", json_type, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["owning_department_id"], ["departments.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
    )
    op.create_index("ix_formalities_code", "formalities", ["code"])
    op.create_index("ix_formalities_owning_department_id", "formalities", ["owning_department_id"])

    op.create_table(
        "formality_departments",
        sa.Column("formality_id", sa.Uuid(), nullable=False),
        sa.Column("department_id", sa.Uuid(), nullable=False),
        sa.Column("relation_type", sa.String(length=16), nullable=False),
        sa.CheckConstraint(
            "relation_type IN ('applied', 'publishing')",
            name="ck_formality_department_relation",
        ),
        sa.ForeignKeyConstraint(["formality_id"], ["formalities.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["department_id"], ["departments.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("formality_id", "department_id", "relation_type"),
    )
    op.create_index(
        "ix_formality_department_department",
        "formality_departments",
        ["department_id", "relation_type"],
    )

    op.create_table(
        "snapshots",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("snapshot_key", sa.String(length=240), nullable=False),
        sa.Column("schema_version", sa.Integer(), nullable=False),
        sa.Column("root_department_id", sa.Uuid(), nullable=False),
        sa.Column("period_type", sa.String(length=16), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("period_value", sa.Integer(), nullable=True),
        sa.Column("scope", sa.String(length=16), nullable=False),
        sa.Column("formality_id", sa.Uuid(), nullable=True),
        sa.Column("state", sa.String(length=16), nullable=False),
        sa.Column("province_aggregated_score", sa.Numeric(10, 4), nullable=True),
        sa.Column("province_aggregated_maximum", sa.Numeric(10, 4), nullable=True),
        sa.Column("policy", json_type, nullable=False),
        sa.Column("status_detail", json_type, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("period_type IN ('month', 'quarter', 'year')", name="ck_snapshot_period"),
        sa.CheckConstraint(
            "(period_type = 'month' AND period_value BETWEEN 1 AND 12) OR "
            "(period_type = 'quarter' AND period_value BETWEEN 1 AND 4) OR "
            "(period_type = 'year' AND period_value IS NULL)",
            name="ck_snapshot_period_value",
        ),
        sa.CheckConstraint("scope IN ('all', 'formality')", name="ck_snapshot_scope"),
        sa.CheckConstraint(
            "(scope = 'all' AND formality_id IS NULL) OR "
            "(scope = 'formality' AND formality_id IS NOT NULL)",
            name="ck_snapshot_formality_scope",
        ),
        sa.CheckConstraint("state IN ('complete', 'incomplete')", name="ck_snapshot_state"),
        sa.ForeignKeyConstraint(["root_department_id"], ["departments.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("snapshot_key"),
    )
    op.create_index("ix_snapshots_created_at", "snapshots", ["created_at"])
    op.create_index("ix_snapshots_root_department_id", "snapshots", ["root_department_id"])
    op.create_index(
        "ix_snapshot_lookup",
        "snapshots",
        ["root_department_id", "period_type", "year", "period_value", "scope"],
    )

    op.create_table(
        "datasets",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("snapshot_id", sa.Uuid(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("group_name", sa.String(length=80), nullable=False),
        sa.Column("schema_kind", sa.String(length=16), nullable=False),
        sa.Column("formula_status", sa.String(length=80), nullable=False),
        sa.Column("score_policy", sa.String(length=40), nullable=False),
        sa.Column("raw_path", sa.Text(), nullable=False),
        sa.Column("raw_sha256", sa.String(length=64), nullable=False),
        sa.Column("details", json_type, nullable=False),
        sa.CheckConstraint("schema_kind IN ('metrics', 'parameters')", name="ck_dataset_schema_kind"),
        sa.CheckConstraint("length(raw_sha256) = 64", name="ck_dataset_raw_sha256"),
        sa.ForeignKeyConstraint(["snapshot_id"], ["snapshots.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("snapshot_id", "group_name", name="uq_dataset_snapshot_group"),
    )
    op.create_index("ix_datasets_snapshot_id", "datasets", ["snapshot_id"])

    op.create_table(
        "entities",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("dataset_id", sa.Uuid(), nullable=False),
        sa.Column("department_id", sa.Uuid(), nullable=False),
        sa.Column("entity_kind", sa.String(length=16), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("api_score", sa.Numeric(10, 4), nullable=True),
        sa.Column("api_max_score", sa.Numeric(10, 4), nullable=True),
        sa.Column("api_ratio", sa.Numeric(12, 6), nullable=True),
        sa.Column("score_source", sa.String(length=40), nullable=False),
        sa.Column("formula_applied", sa.Boolean(), nullable=False),
        sa.Column("parameters", json_type, nullable=False),
        sa.Column("source_metadata", json_type, nullable=False),
        sa.CheckConstraint("entity_kind IN ('root', 'child')", name="ck_entity_kind"),
        sa.ForeignKeyConstraint(["dataset_id"], ["datasets.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["department_id"], ["departments.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("dataset_id", "entity_kind", "department_id", name="uq_entity_dataset_kind_department"),
    )
    op.create_index("ix_entities_dataset_id", "entities", ["dataset_id"])
    op.create_index("ix_entity_department", "entities", ["department_id", "dataset_id"])

    op.create_table(
        "metrics",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("entity_id", sa.BigInteger(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("code", sa.String(length=120), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("numerator", sa.Numeric(24, 6), nullable=True),
        sa.Column("denominator", sa.Numeric(24, 6), nullable=True),
        sa.Column("ratio", sa.Numeric(12, 6), nullable=True),
        sa.Column("api_score", sa.Numeric(10, 4), nullable=True),
        sa.Column("api_max_score", sa.Numeric(10, 4), nullable=True),
        sa.Column("extras", json_type, nullable=False),
        sa.ForeignKeyConstraint(["entity_id"], ["entities.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("entity_id", "code", name="uq_metric_entity_code"),
    )
    op.create_index("ix_metrics_entity_id", "metrics", ["entity_id"])
    op.create_index("ix_metric_code", "metrics", ["code"])

    op.create_table(
        "collection_jobs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("idempotency_key", sa.String(length=240), nullable=False),
        sa.Column("state", sa.String(length=16), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column("request", json_type, nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("next_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("locked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("locked_by", sa.String(length=160), nullable=True),
        sa.Column("error", json_type, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "state IN ('queued', 'running', 'succeeded', 'failed', 'halted')",
            name="ck_collection_job_state",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("idempotency_key"),
    )
    op.create_index(
        "ix_collection_job_claim",
        "collection_jobs",
        ["state", "priority", "next_run_at", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_collection_job_claim", table_name="collection_jobs")
    op.drop_table("collection_jobs")
    op.drop_index("ix_metric_code", table_name="metrics")
    op.drop_index("ix_metrics_entity_id", table_name="metrics")
    op.drop_table("metrics")
    op.drop_index("ix_entity_department", table_name="entities")
    op.drop_index("ix_entities_dataset_id", table_name="entities")
    op.drop_table("entities")
    op.drop_index("ix_datasets_snapshot_id", table_name="datasets")
    op.drop_table("datasets")
    op.drop_index("ix_snapshot_lookup", table_name="snapshots")
    op.drop_index("ix_snapshots_root_department_id", table_name="snapshots")
    op.drop_index("ix_snapshots_created_at", table_name="snapshots")
    op.drop_table("snapshots")
    op.drop_index("ix_formality_department_department", table_name="formality_departments")
    op.drop_table("formality_departments")
    op.drop_index("ix_formalities_owning_department_id", table_name="formalities")
    op.drop_index("ix_formalities_code", table_name="formalities")
    op.drop_table("formalities")
    op.drop_index("ix_departments_code", table_name="departments")
    op.drop_table("departments")
