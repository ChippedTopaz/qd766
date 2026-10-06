"""Account-owned, source-wallet-backed on-demand analysis. No activation/backfill."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
revision = "20261006_0018"
down_revision = "20261005_0017"
branch_labels = depends_on = None

def upgrade():
    json_type=sa.JSON().with_variant(postgresql.JSONB(), "postgresql")
    op.create_table("gemini_analyses",
        sa.Column("id",sa.Uuid(),primary_key=True),
        sa.Column("account_id",sa.Uuid(),sa.ForeignKey("user_accounts.id",ondelete="RESTRICT"),nullable=False),
        sa.Column("request_token",sa.Uuid(),nullable=False),
        sa.Column("context",json_type,nullable=False),sa.Column("evidence",json_type,nullable=False),
        sa.Column("result",json_type),sa.Column("state",sa.String(16),nullable=False),
        sa.Column("model",sa.String(120),nullable=False),
        sa.Column("created_at",sa.DateTime(timezone=True),nullable=False),
        sa.Column("finished_at",sa.DateTime(timezone=True)),
        sa.UniqueConstraint("account_id","request_token",name="uq_gemini_analysis_token"),
        sa.CheckConstraint("state IN ('running', 'ready', 'failed')",name="ck_gemini_analysis_state"))
    op.create_index("ix_gemini_analysis_owner","gemini_analyses",["account_id","created_at"])

def downgrade():
    raise RuntimeError("Review and back up paid analysis history before removal")
