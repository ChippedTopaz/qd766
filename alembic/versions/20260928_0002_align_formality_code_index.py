"""Align the formality code uniqueness with SQLAlchemy metadata.

Revision ID: 20260928_0002
Revises: 20260928_0001
Create Date: 2026-09-28
"""

from alembic import op


revision = "20260928_0002"
down_revision = "20260928_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_index("ix_formalities_code", table_name="formalities")
    op.drop_constraint("formalities_code_key", "formalities", type_="unique")
    op.create_index("ix_formalities_code", "formalities", ["code"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_formalities_code", table_name="formalities")
    op.create_unique_constraint("formalities_code_key", "formalities", ["code"])
    op.create_index("ix_formalities_code", "formalities", ["code"], unique=False)
