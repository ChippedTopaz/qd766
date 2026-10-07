"""Independent question bank, persistent player progress and idempotent answers."""
from alembic import op
import sqlalchemy as sa
revision='20261007_0023'
down_revision='20261007_0022'
branch_labels=depends_on=None

def upgrade():
    op.create_table('trivia_questions',
        sa.Column('id',sa.Uuid(),primary_key=True),sa.Column('prompt',sa.Text(),nullable=False),
        sa.Column('choices',sa.JSON(),nullable=False),sa.Column('correct_index',sa.Integer(),nullable=False),
        sa.Column('explanation',sa.Text(),nullable=False),sa.Column('state',sa.String(16),nullable=False),
        sa.Column('locked',sa.Boolean(),nullable=False),sa.Column('revision',sa.Integer(),nullable=False),
        sa.Column('created_at',sa.DateTime(timezone=True),server_default=sa.func.now(),nullable=False),
        sa.CheckConstraint("state IN ('draft','published','retired')",name='ck_trivia_state'))
    op.create_table('trivia_profiles',
        sa.Column('account_id',sa.Uuid(),sa.ForeignKey('user_accounts.id',ondelete='CASCADE'),primary_key=True),
        sa.Column('pending_id',sa.Uuid(),sa.ForeignKey('trivia_questions.id',ondelete='SET NULL')),
        sa.Column('pending_deadline',sa.DateTime(timezone=True)),
        sa.Column('round_id',sa.Uuid(),nullable=False),
        *[sa.Column(name,sa.Integer(),nullable=False) for name in ('score','streak','best','answered')])
    op.create_table('trivia_answers',
        sa.Column('account_id',sa.Uuid(),sa.ForeignKey('user_accounts.id',ondelete='CASCADE'),primary_key=True),
        sa.Column('question_id',sa.Uuid(),sa.ForeignKey('trivia_questions.id',ondelete='RESTRICT'),primary_key=True),
        sa.Column('round_id',sa.Uuid(),primary_key=True),
        sa.Column('choice',sa.Integer()),sa.Column('correct',sa.Boolean(),nullable=False),
        sa.Column('timed_out',sa.Boolean(),nullable=False),
        *[sa.Column(name,sa.Integer(),nullable=False) for name in ('score_after','streak_after','best_after','answered_after')],
        sa.Column('created_at',sa.DateTime(timezone=True),server_default=sa.func.now(),nullable=False))
    op.create_index('ix_trivia_answers_question_correct_account','trivia_answers',['question_id','correct','account_id'])

def downgrade():
    op.drop_table('trivia_answers');op.drop_table('trivia_profiles');op.drop_table('trivia_questions')
