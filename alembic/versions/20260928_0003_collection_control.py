"""Add the global collection circuit breaker and worker lease.

Revision ID: 20260928_0003
Revises: 20260928_0002
Create Date: 2026-09-28
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260928_0003"
down_revision = "20260928_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "collection_controls",
        sa.Column("key", sa.String(length=80), nullable=False),
        sa.Column("circuit_state", sa.String(length=16), nullable=False),
        sa.Column("reason", sa.String(length=160), nullable=True),
        sa.Column("detail", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("opened_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("lease_locked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("lease_locked_by", sa.String(length=160), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "circuit_state IN ('closed', 'open')",
            name="ck_collection_control_circuit_state",
        ),
        sa.PrimaryKeyConstraint("key"),
    )
    controls = sa.table(
        "collection_controls",
        sa.column("key", sa.String),
        sa.column("circuit_state", sa.String),
    )
    op.bulk_insert(controls, [{"key": "dvcqg", "circuit_state": "closed"}])


def downgrade() -> None:
    op.drop_table("collection_controls")
