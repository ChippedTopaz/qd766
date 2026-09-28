from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .cache import SingleFlightTTLCache
from .config import Settings
from .database import create_database_engine, create_session_factory
from .routes import router


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved = settings or Settings.from_env()
    engine = create_database_engine(resolved)
    app = FastAPI(title="QD766 API", version="0.2.0")
    app.state.settings = resolved
    app.state.engine = engine
    app.state.session_factory = create_session_factory(engine)
    app.state.dashboard_cache = SingleFlightTTLCache[str, dict](
        resolved.dashboard_cache_ttl_seconds
    )
    if resolved.cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=list(resolved.cors_origins),
            allow_credentials=False,
            allow_methods=["GET", "POST"],
            allow_headers=["*"],
        )
    app.include_router(router)
    web_root = Path(__file__).resolve().parents[3] / "web"
    if web_root.is_dir():
        app.mount("/", StaticFiles(directory=web_root, html=True), name="web")
    return app
