"""Public Google-verified application profiles; no existing access/grants changed."""
from alembic import op
import sqlalchemy as sa
revision='20261009_0025'
down_revision='20261008_0024'
branch_labels=depends_on=None

def upgrade():
    op.add_column('login_attempts',sa.Column('public_registration',sa.Boolean(),nullable=False,server_default=sa.false()))
    op.alter_column('trial_registrations','link_id',existing_type=sa.Uuid(),nullable=True)
    op.add_column('trial_registrations',sa.Column('requested_tier',sa.String(16),nullable=False,server_default='agency'))
    op.add_column('trial_registrations',sa.Column('full_name',sa.String(160)))
    op.add_column('trial_registrations',sa.Column('birth_date',sa.Date()))
    op.add_column('trial_registrations',sa.Column('gender',sa.String(16)))
    op.add_column('trial_registrations',sa.Column('workplace',sa.String(240)))
    op.drop_constraint('ck_registration_scope','trial_registrations',type_='check')
    op.create_check_constraint('ck_registration_scope','trial_registrations',"state = 'draft' OR (root_department_id IS NOT NULL AND ((requested_tier = 'agency' AND unit_department_id IS NOT NULL) OR (requested_tier = 'province' AND unit_department_id IS NULL)))")
    op.create_check_constraint('ck_registration_tier','trial_registrations',"requested_tier IN ('province','agency')")
    op.create_check_constraint('ck_registration_link_tier','trial_registrations',"link_id IS NULL OR requested_tier = 'agency'")

def downgrade():
    # Public applications have no invitation link. Do not silently erase their
    # profiles or make link_id NOT NULL when rolling back application code.
    raise RuntimeError('Preserve registration profiles; restore a reviewed backup for schema rollback.')
