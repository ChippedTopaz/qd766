"""Google identity, expiring login challenges and revocable sessions."""
from alembic import op
import sqlalchemy as sa

revision = "20261002_0009"
down_revision = "20261002_0008"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("user_accounts", sa.Column("email", sa.String(320), nullable=True))
    op.add_column("user_accounts", sa.Column("root_department_id", sa.Uuid(), nullable=True))
    op.create_foreign_key("fk_account_root_department", "user_accounts", "departments", ["root_department_id"], ["id"], ondelete="RESTRICT")
    op.create_index("ix_user_accounts_root_department_id", "user_accounts", ["root_department_id"])
    op.create_table("login_attempts",
        sa.Column("state_hash", sa.String(64), primary_key=True),
        sa.Column("binding_hash", sa.String(64), nullable=False),
        sa.Column("nonce", sa.String(80), nullable=False),
        sa.Column("verifier", sa.String(100), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True)))
    op.create_index("ix_login_attempts_expires_at", "login_attempts", ["expires_at"])
    op.create_table("login_sessions",
        sa.Column("token_hash", sa.String(64), primary_key=True),
        sa.Column("account_id", sa.Uuid(), sa.ForeignKey("user_accounts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("csrf_token", sa.String(80), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False))
    op.create_index("ix_login_sessions_account_id", "login_sessions", ["account_id"])
    op.create_index("ix_login_sessions_expires_at", "login_sessions", ["expires_at"])


def downgrade():
    op.drop_table("login_sessions")
    op.drop_table("login_attempts")
    op.drop_index("ix_user_accounts_root_department_id", table_name="user_accounts")
    op.drop_constraint("fk_account_root_department", "user_accounts", type_="foreignkey")
    op.drop_column("user_accounts", "root_department_id")
    op.drop_column("user_accounts", "email")
