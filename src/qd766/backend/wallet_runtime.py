"""Fail-closed real wallet configuration; public launcher remains disabled."""
from sqlalchemy.engine import make_url
from sqlalchemy import inspect, text


def validate_wallet_runtime(settings):
    if settings.wallet_requests_paused and not settings.real_wallet_enabled:
        raise ValueError("Paid request pause requires explicit real wallet mode")
    if settings.source_wallet_trial and not settings.local_google_trial:
        raise ValueError("Source wallet trial requires isolated local Google mode")
    if not settings.real_wallet_enabled:
        return
    if settings.local_google_trial or settings.source_wallet_trial:
        raise ValueError("Real wallet cannot run in simulation mode")
    if not (settings.public_read_only and settings.require_login and settings.invite_required
            and settings.paid_requests_enabled and settings.trial_credits_enabled
            and settings.trial_credit_management):
        raise ValueError("Real wallet requires authenticated invite-only collection boundary")
    if settings.formality_credit_cost != 5 or settings.sql_echo:
        raise ValueError("Real wallet requires approved Credit value and private SQL logging")
    if settings.google_redirect_uri not in {
            "https://api.bochiso766.com/api/v1/auth/google/callback",
            "https://bochiso766.com/api/v1/auth/google/callback"}:
        raise ValueError("Real wallet requires approved public HTTPS callback")
    database = make_url(settings.database_url)
    if (database.drivername != "postgresql+psycopg"
            or database.host not in {"localhost", "127.0.0.1", "::1"}
            or not database.database or database.database == "qd766_credit_test"
            or database.query):
        raise ValueError("Real wallet requires explicit office PostgreSQL without trial schema options")


def verify_real_wallet_schema(factory, *, shared_registration=False):
    """Before a real lifespan starts: inspect schema read-only, never run migrations."""
    from .models import Base
    with factory() as db:
        if db.get_bind().dialect.name != "postgresql":
            raise ValueError("Real wallet requires PostgreSQL")
        db.execute(text("SET TRANSACTION READ ONLY"))
        db.execute(text("SET LOCAL statement_timeout = '15s'"))
        inspector = inspect(db.connection())
        required = ("credit_lots", "credit_holds", "credit_wallet_events", "subscription_cycles",
                    "credit_wallet_enrollments", "account_collection_permissions")
        for name in required:
            actual = {column["name"] for column in inspector.get_columns(name, schema="public")}
            if not set(Base.metadata.tables[name].columns.keys()) <= actual:
                raise ValueError("Wallet schema is incomplete")
        revisions = list(db.execute(text("SELECT version_num FROM public.alembic_version")).scalars())
        reviewed_revisions = {"20261004_0015", "20261005_0016", "20261005_0017", "20261006_0018", "20261007_0019", "20261007_0020", "20261007_0021", "20261007_0022", "20261007_0023", "20261008_0024"}
        if len(revisions) != 1 or revisions[0] not in reviewed_revisions:
            raise ValueError("Wallet schema version has not been reviewed")
        if shared_registration and revisions[0] == '20261004_0015':
            raise ValueError("Shared registration schema has not been migrated")
        # Reviewed additive upgrades must include their actual tables, not just
        # a claimed version number. Never accept arbitrary future revisions.
        extra = []
        if revisions[0] in reviewed_revisions-{"20261004_0015"}:
            extra += ["shared_trial_links", "shared_trial_logins", "trial_registrations"]
        if revisions[0] in reviewed_revisions-{"20261004_0015","20261005_0016"}:
            extra += ["daily_observations"]
        if revisions[0] in {"20261006_0018", "20261007_0019", "20261007_0020", "20261007_0021", "20261007_0022", "20261007_0023", "20261008_0024"}:
            extra += ["gemini_analyses"]
        if revisions[0] in {"20261007_0019", "20261007_0020", "20261007_0021", "20261007_0022", "20261007_0023", "20261008_0024"}:
            extra += ["analysis_queue_entries"]
        if revisions[0] in {"20261007_0020", "20261007_0021", "20261007_0022", "20261007_0023", "20261008_0024"}:
            extra += ['analysis_config_revisions','analysis_config_head']
        if revisions[0] in {"20261007_0021", "20261007_0022", "20261007_0023", "20261008_0024"}:
            extra += ['analysis_group_config_revisions']
        if revisions[0] in {"20261007_0022", "20261007_0023", "20261008_0024"}:
            extra += ['analysis_feature_control']
        if revisions[0] in {"20261007_0023", "20261008_0024"}:
            extra += ['trivia_questions','trivia_profiles','trivia_answers']
        if revisions[0] == "20261008_0024":
            extra += ['formula_config_revisions','formula_config_head']
        for name in extra:
            actual = {column["name"] for column in inspector.get_columns(name, schema="public")}
            if not set(Base.metadata.tables[name].columns.keys()) <= actual:
                raise ValueError("Reviewed additive schema is incomplete")
        # Session closes with rollback; no financial mutation or migration.
