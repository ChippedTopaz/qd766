"""Add versioned national summary snapshots.

Revision ID: 20261001_0006
Revises: 20261001_0005
Create Date: 2026-10-01
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20261001_0006"
down_revision = "20261001_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    json_type = postgresql.JSONB(astext_type=sa.Text())
    op.create_table(
        "national_summary_snapshots",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("summary_key", sa.String(length=240), nullable=False),
        sa.Column("period_type", sa.String(length=16), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("period_value", sa.Integer(), nullable=True),
        sa.Column("department_type", sa.String(length=40), nullable=False),
        sa.Column("province_count", sa.Integer(), nullable=False),
        sa.Column("raw_sha256", sa.String(length=64), nullable=False),
        sa.Column("request_payload", json_type, nullable=False),
        sa.Column("response_data", json_type, nullable=False),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "period_type IN ('month', 'quarter', 'year')",
            name="ck_national_summary_period",
        ),
        sa.CheckConstraint(
            "(period_type = 'month' AND period_value BETWEEN 1 AND 12) OR "
            "(period_type = 'quarter' AND period_value BETWEEN 1 AND 4) OR "
            "(period_type = 'year' AND period_value IS NULL)",
            name="ck_national_summary_period_value",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("summary_key"),
    )
    op.create_index(
        "ix_national_summary_snapshots_captured_at",
        "national_summary_snapshots",
        ["captured_at"],
    )
    op.create_index(
        "ix_national_summary_lookup",
        "national_summary_snapshots",
        ["period_type", "year", "period_value", "captured_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_national_summary_lookup", table_name="national_summary_snapshots"
    )
    op.drop_index(
        "ix_national_summary_snapshots_captured_at",
        table_name="national_summary_snapshots",
    )
    op.drop_table("national_summary_snapshots")
