"""Record the six-group completeness contract for national summaries.

Revision ID: 20261002_0008
Revises: 20261002_0007
Create Date: 2026-10-02
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20261002_0008"
down_revision = "20261002_0007"
branch_labels = None
depends_on = None


GROUP_CODES = '["CKMB", "CLGQ", "MDHL", "MDSH", "TDGQ", "TTTT"]'


def upgrade() -> None:
    op.add_column(
        "national_summary_snapshots",
        sa.Column("completeness_state", sa.String(length=16), nullable=True),
    )
    op.add_column(
        "national_summary_snapshots",
        sa.Column("group_count", sa.Integer(), nullable=True),
    )
    op.add_column(
        "national_summary_snapshots",
        sa.Column("group_codes", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.execute(
        sa.text(
            "UPDATE national_summary_snapshots "
            "SET completeness_state = 'complete', group_count = 6, "
            "group_codes = CAST(:codes AS jsonb)"
        ).bindparams(codes=GROUP_CODES)
    )
    op.alter_column("national_summary_snapshots", "completeness_state", nullable=False)
    op.alter_column("national_summary_snapshots", "group_count", nullable=False)
    op.alter_column("national_summary_snapshots", "group_codes", nullable=False)
    op.create_check_constraint(
        "ck_national_summary_completeness_state",
        "national_summary_snapshots",
        "completeness_state = 'complete'",
    )
    op.create_check_constraint(
        "ck_national_summary_group_count",
        "national_summary_snapshots",
        "group_count = 6",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_national_summary_group_count",
        "national_summary_snapshots",
        type_="check",
    )
    op.drop_constraint(
        "ck_national_summary_completeness_state",
        "national_summary_snapshots",
        type_="check",
    )
    op.drop_column("national_summary_snapshots", "group_codes")
    op.drop_column("national_summary_snapshots", "group_count")
    op.drop_column("national_summary_snapshots", "completeness_state")
