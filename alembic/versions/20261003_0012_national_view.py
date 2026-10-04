"""National viewer scope, independent of administrator role. Not applied to production."""
from alembic import op
from sqlalchemy import text

revision = "20261003_0012"
down_revision = "20261003_0011"
branch_labels = None
depends_on = None

def upgrade():
    for table,name in (("user_accounts","ck_account_access_tier"),("trial_invitations","ck_invite_tier")):
        op.drop_constraint(name,table,type_="check")
        op.create_check_constraint(name,table,"access_tier IN ('province', 'agency', 'national')")

def downgrade():
    connection=op.get_bind()
    for table in ("user_accounts","trial_invitations"):
        if connection.execute(text(f"SELECT count(*) FROM {table} WHERE access_tier='national'")).scalar():
            raise RuntimeError("Reassign national scopes before downgrade; no silent permission changes")
    for table,name in (("user_accounts","ck_account_access_tier"),("trial_invitations","ck_invite_tier")):
        op.drop_constraint(name,table,type_="check")
        op.create_check_constraint(name,table,"access_tier IN ('province', 'agency')")
