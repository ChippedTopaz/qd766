from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from qd766.province_catalog import AmSieuTocCatalogClient, ProvinceCatalog

from .cache import SingleFlightTTLCache
from .config import Settings
from .database import create_database_engine, create_session_factory
from .routes import router
from .access_policy import enforce_public_read_only


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved = settings or Settings.from_env()
    if resolved.public_read_only and "*" in resolved.cors_origins:
        raise ValueError("Public preview requires explicit CORS origins, not '*'")
    engine = create_database_engine(resolved)
    app = FastAPI(title="QD766 API", version="0.2.0", docs_url=None if resolved.public_read_only else "/docs",
                  redoc_url=None if resolved.public_read_only else "/redoc",
                  openapi_url=None if resolved.public_read_only else "/openapi.json")
    app.state.settings = resolved
    app.middleware("http")(enforce_public_read_only)

    @app.get("/api/v1/access-policy", tags=["health"])
    def access_policy() -> dict:
        return {"publicReadOnly": resolved.public_read_only,
                "authenticated": False, "paidRequestsEnabled": False}
    app.state.engine = engine
    app.state.session_factory = create_session_factory(engine)
    app.state.dashboard_cache = SingleFlightTTLCache[str, dict](
        resolved.dashboard_cache_ttl_seconds
    )
    app.state.province_catalog_client = AmSieuTocCatalogClient(
        resolved.province_catalog_index_url,
        resolved.province_catalog_version_url,
        resolved.province_catalog_rules_url,
        timeout_seconds=resolved.province_catalog_timeout_seconds,
    )
    app.state.province_catalog_cache = SingleFlightTTLCache[str, ProvinceCatalog](
        resolved.province_catalog_cache_ttl_seconds
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
