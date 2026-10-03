"""Invite-only trial, administrator role and agency scope."""
from alembic import op
import sqlalchemy as sa

revision = "20261003_0010"
down_revision = "20261002_0009"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("user_accounts", sa.Column("role", sa.String(16), nullable=False, server_default="user"))
    op.add_column("user_accounts", sa.Column("trial_admitted", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("user_accounts", sa.Column("access_tier", sa.String(16), nullable=False, server_default="province"))
    op.add_column("user_accounts", sa.Column("unit_department_id", sa.Uuid(), sa.ForeignKey("departments.id", ondelete="RESTRICT")))
    op.create_check_constraint("ck_account_role", "user_accounts", "role IN ('user', 'admin')")
    op.create_check_constraint("ck_account_access_tier", "user_accounts", "access_tier IN ('province', 'agency')")
    op.create_check_constraint("ck_account_unit_scope", "user_accounts", "access_tier != 'agency' OR (unit_department_id IS NOT NULL AND root_department_id IS NOT NULL)")
    op.create_table("trial_invitations",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("created_by", sa.Uuid(), sa.ForeignKey("user_accounts.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("recipient_email", sa.String(320)),
        sa.Column("root_department_id", sa.Uuid(), sa.ForeignKey("departments.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("access_tier", sa.String(16), nullable=False),
        sa.Column("unit_department_id", sa.Uuid(), sa.ForeignKey("departments.id", ondelete="RESTRICT")),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.Column("used_at", sa.DateTime(timezone=True)),
        sa.Column("used_by", sa.Uuid(), sa.ForeignKey("user_accounts.id", ondelete="RESTRICT")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("access_tier IN ('province', 'agency')", name="ck_invite_tier"),
        sa.CheckConstraint("access_tier != 'agency' OR unit_department_id IS NOT NULL", name="ck_invite_unit"))
    op.add_column("login_attempts", sa.Column("invitation_id", sa.Uuid(), sa.ForeignKey("trial_invitations.id", ondelete="SET NULL")))
    op.create_table("admin_audits",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("actor_id", sa.Uuid(), sa.ForeignKey("user_accounts.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("action", sa.String(80), nullable=False),
        sa.Column("details", sa.JSON().with_variant(sa.dialects.postgresql.JSONB(), "postgresql"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()))


def downgrade():
    op.drop_table("admin_audits")
    op.drop_column("login_attempts", "invitation_id")
    op.drop_table("trial_invitations")
    for name in ("ck_account_unit_scope", "ck_account_access_tier", "ck_account_role"):
        op.drop_constraint(name, "user_accounts", type_="check")
    for name in ("unit_department_id", "access_tier", "trial_admitted", "role"):
        op.drop_column("user_accounts", name)
