from __future__ import annotations

from collections.abc import Iterator

from fastapi import Request
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from .config import Settings


def create_database_engine(settings: Settings) -> Engine:
    options: dict[str, object] = {
        "pool_pre_ping": True,
        "echo": settings.sql_echo,
    }
    if settings.database_url in {"sqlite://", "sqlite+pysqlite://"}:
        options.update(
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
    if settings.real_wallet_enabled:
        options["connect_args"] = {"options": "-c search_path=public"}
    return create_engine(settings.database_url, **options)


def create_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_session(request: Request) -> Iterator[Session]:
    factory: sessionmaker[Session] = request.app.state.session_factory
    with factory() as session:
        yield session
