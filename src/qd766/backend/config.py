from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from sqlalchemy.engine import URL

DEFAULT_DATABASE_URL = "postgresql+psycopg://qd766_app@127.0.0.1:5432/qd766"


def load_environment_file(path: Path) -> None:
    """Load a simple local .env file without overwriting process settings."""

    for line in path.read_text(encoding="utf-8").splitlines():
        value = line.strip()
        if not value or value.startswith("#"):
            continue
        name, separator, setting = value.partition("=")
        if separator:
            os.environ.setdefault(name, setting)


def _as_bool(value: str | None) -> bool:
    return (value or "").strip().lower() in {"1", "true", "yes", "on"}


def _positive_float(value: str | None, default: float) -> float:
    if value is None:
        return default
    parsed = float(value)
    if parsed <= 0:
        raise ValueError("cache TTL must be positive")
    return parsed


def _database_url_from_env() -> str:
    explicit_url = os.getenv("QD766_DATABASE_URL")
    if explicit_url:
        return explicit_url

    password = os.getenv("QD766_DATABASE_PASSWORD")
    if password is None:
        return DEFAULT_DATABASE_URL

    return URL.create(
        drivername="postgresql+psycopg",
        username=os.getenv("QD766_DATABASE_USER", "qd766_app"),
        password=password,
        host=os.getenv("QD766_DATABASE_HOST", "127.0.0.1"),
        port=int(os.getenv("QD766_DATABASE_PORT", "5432")),
        database=os.getenv("QD766_DATABASE_NAME", "qd766"),
    ).render_as_string(hide_password=False)


@dataclass(frozen=True)
class Settings:
    gemini_analysis_enabled: bool = False
    gemini_queue_enabled: bool = False
    gemini_api_key: str = field(default="", repr=False)
    gemini_model: str = ""
    public_read_only: bool = False
    require_login: bool = False
    invite_required: bool = False
    shared_registration_enabled: bool = False  # Explicit activation after schema migration; local trial first.
    paid_requests_enabled: bool = False
    formality_credit_cost: int = 0
    trial_credits_enabled: bool = False
    trial_credit_management: bool = False
    local_google_trial: bool = False  # Explicit launcher only; never inherited from environment.
    source_wallet_trial: bool = False  # Explicit isolated launcher only; not read from environment.
    real_wallet_enabled: bool = False  # Prepared opt-in only; never inherited from environment.
    wallet_requests_paused: bool = False  # Keep reads/settlement/cycles; pause new paid requests only.
    google_client_id: str = ""
    google_client_secret: str = field(default="", repr=False)
    google_redirect_uri: str = ""
    database_url: str = DEFAULT_DATABASE_URL
    cors_origins: tuple[str, ...] = ()
    sql_echo: bool = False
    dashboard_cache_ttl_seconds: float = 60.0
    province_catalog_index_url: str = (
        "https://raw.githubusercontent.com/ChippedTopaz/am-sieu-toc-data/data/index.json"
    )
    province_catalog_version_url: str = (
        "https://raw.githubusercontent.com/ChippedTopaz/am-sieu-toc-data/data/version.json"
    )
    province_catalog_rules_url: str = (
        "https://raw.githubusercontent.com/ChippedTopaz/am-sieu-toc-data/niemyet/isVertical.json"
    )
    province_catalog_cache_ttl_seconds: float = 3600.0
    province_catalog_timeout_seconds: float = 30.0

    @property
    def source_wallet_enabled(self) -> bool:
        return self.source_wallet_trial or self.real_wallet_enabled

    @classmethod
    def from_env(cls) -> "Settings":
        origins = tuple(
            item.strip()
            for item in os.getenv("QD766_CORS_ORIGINS", "").split(",")
            if item.strip()
        )
        return cls(
            gemini_analysis_enabled=_as_bool(os.getenv("QD766_GEMINI_ANALYSIS_ENABLED")),
            gemini_queue_enabled=_as_bool(os.getenv("QD766_GEMINI_QUEUE_ENABLED")),
            gemini_api_key=os.getenv("QD766_GEMINI_API_KEY", ""),
            gemini_model=os.getenv("QD766_GEMINI_MODEL", ""),
            public_read_only=_as_bool(os.getenv("QD766_PUBLIC_READ_ONLY")),
            require_login=_as_bool(os.getenv("QD766_REQUIRE_LOGIN")),
            invite_required=_as_bool(os.getenv("QD766_INVITE_REQUIRED")),
            paid_requests_enabled=_as_bool(os.getenv("QD766_PAID_REQUESTS_ENABLED")),
            formality_credit_cost=int(os.getenv("QD766_FORMALITY_CREDIT_COST", "0")),
            trial_credits_enabled=_as_bool(os.getenv("QD766_TRIAL_CREDITS_ENABLED")),
            google_client_id=os.getenv("QD766_GOOGLE_CLIENT_ID", ""),
            google_client_secret=os.getenv("QD766_GOOGLE_CLIENT_SECRET", ""),
            google_redirect_uri=os.getenv("QD766_GOOGLE_REDIRECT_URI", ""),
            database_url=_database_url_from_env(),
            cors_origins=origins,
            sql_echo=_as_bool(os.getenv("QD766_SQL_ECHO")),
            dashboard_cache_ttl_seconds=_positive_float(
                os.getenv("QD766_DASHBOARD_CACHE_TTL_SECONDS"),
                60.0,
            ),
            province_catalog_index_url=os.getenv(
                "QD766_PROVINCE_CATALOG_INDEX_URL", cls.province_catalog_index_url
            ),
            province_catalog_version_url=os.getenv(
                "QD766_PROVINCE_CATALOG_VERSION_URL", cls.province_catalog_version_url
            ),
            province_catalog_rules_url=os.getenv(
                "QD766_PROVINCE_CATALOG_RULES_URL", cls.province_catalog_rules_url
            ),
            province_catalog_cache_ttl_seconds=_positive_float(
                os.getenv("QD766_PROVINCE_CATALOG_CACHE_TTL_SECONDS"),
                3600.0,
            ),
            province_catalog_timeout_seconds=_positive_float(
                os.getenv("QD766_PROVINCE_CATALOG_TIMEOUT_SECONDS"),
                30.0,
            ),
        )
