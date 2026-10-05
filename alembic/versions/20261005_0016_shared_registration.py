"""Agency-only shared registration links, review required before admission."""
from alembic import op
import sqlalchemy as sa

revision = "20261005_0016"
down_revision = "20261004_0015"
branch_labels = depends_on = None


def upgrade():
    op.create_table("shared_trial_links",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("created_by", sa.Uuid(), sa.ForeignKey("user_accounts.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("max_registrations", sa.Integer(), nullable=False),
        sa.Column("registered_count", sa.Integer(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("max_registrations > 0 AND registered_count >= 0 AND registered_count <= max_registrations", name="ck_shared_link_capacity"))
    op.create_table("shared_trial_logins",
        sa.Column("state_hash", sa.String(64), sa.ForeignKey("login_attempts.state_hash", ondelete="CASCADE"), primary_key=True),
        sa.Column("link_id", sa.Uuid(), sa.ForeignKey("shared_trial_links.id", ondelete="RESTRICT"), nullable=False))
    op.create_table("trial_registrations",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("account_id", sa.Uuid(), sa.ForeignKey("user_accounts.id", ondelete="RESTRICT"), nullable=False, unique=True),
        sa.Column("link_id", sa.Uuid(), sa.ForeignKey("shared_trial_links.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("state", sa.String(16), nullable=False),
        sa.Column("root_department_id", sa.Uuid(), sa.ForeignKey("departments.id", ondelete="RESTRICT")),
        sa.Column("unit_department_id", sa.Uuid(), sa.ForeignKey("departments.id", ondelete="RESTRICT")),
        sa.Column("reviewed_by", sa.Uuid(), sa.ForeignKey("user_accounts.id", ondelete="RESTRICT")),
        sa.Column("submitted_at", sa.DateTime(timezone=True)),
        sa.Column("reviewed_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("state IN ('draft','pending','approved','rejected')", name="ck_registration_state"),
        sa.CheckConstraint("state = 'draft' OR (root_department_id IS NOT NULL AND unit_department_id IS NOT NULL)", name="ck_registration_scope"))


def downgrade():
    if op.get_bind().execute(sa.text("SELECT count(*) FROM trial_registrations")).scalar():
        raise RuntimeError("Registrations exist; use a reviewed rollback")
    op.drop_table("trial_registrations")
    op.drop_table("shared_trial_logins")
    op.drop_table("shared_trial_links")
