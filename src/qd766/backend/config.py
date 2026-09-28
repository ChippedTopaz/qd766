from __future__ import annotations

import os
from dataclasses import dataclass
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
    database_url: str = DEFAULT_DATABASE_URL
    cors_origins: tuple[str, ...] = ()
    sql_echo: bool = False

    @classmethod
    def from_env(cls) -> "Settings":
        origins = tuple(
            item.strip()
            for item in os.getenv("QD766_CORS_ORIGINS", "").split(",")
            if item.strip()
        )
        return cls(
            database_url=_database_url_from_env(),
            cors_origins=origins,
            sql_echo=_as_bool(os.getenv("QD766_SQL_ECHO")),
        )
