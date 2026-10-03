"""Isolated, fail-closed office tunnel instance. Never inherit operator flags."""
from pathlib import Path
from sqlalchemy.engine import URL, make_url

from .auth import validate_auth_settings
from .config import Settings

PUBLIC_HOST = "api.bochiso766.com"
PUBLIC_PORT = 8769
CALLBACK = f"https://{PUBLIC_HOST}/api/v1/auth/google/callback"
WEBSITE_CALLBACK = "https://bochiso766.com/api/v1/auth/google/callback"
AUTH_KEYS = frozenset({"QD766_GOOGLE_CLIENT_ID", "QD766_GOOGLE_CLIENT_SECRET",
                       "QD766_GOOGLE_REDIRECT_URI"})


def read_config(path: Path) -> dict[str, str]:
    """Same simple key=value convention as office .env; never log values."""
    result = {}
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        key, separator, value = line.partition("=")
        key = key.strip()
        if not separator or not key or key in result:
            raise ValueError("Invalid or duplicate configuration entry")
        result[key] = value.strip()
    return result


def public_settings(office: dict[str, str], public: dict[str, str]) -> Settings:
    if set(public) != AUTH_KEYS:
        raise ValueError("Public configuration must contain only the three Google settings")
    if any(not value or value.startswith("<") for value in public.values()):
        raise ValueError("Google configuration is incomplete")
    if not public["QD766_GOOGLE_CLIENT_ID"].endswith(".apps.googleusercontent.com"):
        raise ValueError("A Google Web application client ID is required")
    if public["QD766_GOOGLE_REDIRECT_URI"] not in {CALLBACK, WEBSITE_CALLBACK}:
        raise ValueError("Google callback must match the approved public HTTPS address")
    # Share only database connection settings, not operator/auth/rate/credit flags.
    url = office.get("QD766_DATABASE_URL")
    if not url:
        if not office.get("QD766_DATABASE_PASSWORD"):
            raise ValueError("Office PostgreSQL connection is not configured")
        url = URL.create("postgresql+psycopg",
            username=office.get("QD766_DATABASE_USER", "qd766_app"),
            password=office["QD766_DATABASE_PASSWORD"],
            host=office.get("QD766_DATABASE_HOST", "127.0.0.1"),
            port=int(office.get("QD766_DATABASE_PORT", "5432")),
            database=office.get("QD766_DATABASE_NAME", "qd766"))
    parsed = make_url(url)
    if parsed.drivername != "postgresql+psycopg" or parsed.host not in {"127.0.0.1", "localhost"}:
        raise ValueError("Public instance must use office loopback PostgreSQL")
    settings = Settings(database_url=parsed.render_as_string(hide_password=False),
        public_read_only=True, require_login=True,
        paid_requests_enabled=False, trial_credits_enabled=False, formality_credit_cost=0,
        sql_echo=False, cors_origins=(),
        google_client_id=public["QD766_GOOGLE_CLIENT_ID"],
        google_client_secret=public["QD766_GOOGLE_CLIENT_SECRET"],
        google_redirect_uri=public["QD766_GOOGLE_REDIRECT_URI"])
    validate_auth_settings(settings)
    return settings
