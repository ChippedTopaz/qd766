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
from .auth import enabled, validate_auth_settings, router as auth_router
from .user_collection import router as user_collection_router
from .admin import router as admin_router
from .trial_registration import router as registration_router
from .subscription_scheduler import local_credit_lifespan
from .wallet_runtime import validate_wallet_runtime
from .dashboard_transport import DashboardGZipMiddleware


def create_app(settings: Settings | None = None, *, web_root: Path | None = None) -> FastAPI:
    resolved = settings or Settings.from_env()
    validate_auth_settings(resolved)
    validate_wallet_runtime(resolved)
    if resolved.gemini_queue_enabled and not (resolved.gemini_analysis_enabled and resolved.source_wallet_enabled):
        raise ValueError('Analysis queue requires explicitly enabled Gemini and source wallet')
    if resolved.shared_registration_enabled and not (resolved.require_login and resolved.invite_required and resolved.source_wallet_enabled):
        raise ValueError("Shared registration requires invite-only authentication and source wallet")
    if resolved.paid_requests_enabled and (not resolved.require_login or resolved.formality_credit_cost <= 0):
        raise ValueError("TTHC user collection requires authenticated deployment and configured positive credit cost")
    if resolved.trial_credit_management and not (resolved.paid_requests_enabled and resolved.trial_credits_enabled):
        raise ValueError("Trial credit management requires trial collection mode")
    if resolved.public_read_only and "*" in resolved.cors_origins:
        raise ValueError("Public preview requires explicit CORS origins, not '*'")
    engine = create_database_engine(resolved)
    app = FastAPI(title="QD766 API", version="0.2.0", lifespan=local_credit_lifespan,
                  docs_url=None if resolved.public_read_only else "/docs",
                  redoc_url=None if resolved.public_read_only else "/redoc",
                  openapi_url=None if resolved.public_read_only else "/openapi.json")
    app.state.settings = resolved
    from .presence import PresenceTracker, router as presence_router
    app.state.presence=PresenceTracker()
    app.include_router(presence_router)
    if resolved.local_google_trial:
        from starlette.responses import JSONResponse
        @app.middleware("http")
        async def local_google_loopback_only(request, call_next):
            if (request.url.hostname != "127.0.0.1" or request.client.host not in {"127.0.0.1", "::1"}
                    or request.headers.get("origin", "http://127.0.0.1:8771") != "http://127.0.0.1:8771"):
                return JSONResponse({"detail": "Local Google trial is loopback-only"}, status_code=403)
            return await call_next(request)
    app.middleware("http")(enforce_public_read_only)

    @app.get("/api/v1/access-policy", tags=["health"])
    def access_policy() -> dict:
        return {"publicReadOnly": resolved.public_read_only,
                "groupExcelExportEnabled": True,
                "collectionMonitorEnabled": True,
                **({"geminiAnalysisEnabled": True} if resolved.gemini_analysis_enabled else {}),
                **({"geminiAnalysisQueueEnabled": True} if resolved.gemini_queue_enabled else {}),
                "loginRequired": resolved.require_login,
                "googleLoginEnabled": enabled(resolved), "paidRequestsEnabled": resolved.paid_requests_enabled,
                "inviteRequired": resolved.invite_required,
                **({"sharedRegistrationEnabled": True} if resolved.shared_registration_enabled else {}),
                "trialCreditManagement": resolved.trial_credit_management,
                **({"defaultCollectionAccess": True} if resolved.source_wallet_enabled else {}),
                **({"collectionRequestsPaused": resolved.wallet_requests_paused} if resolved.real_wallet_enabled else {}),
                "localSimulation": bool(getattr(app.state, "local_credit_trial", False)),
                **({"localGoogleTrial": True} if resolved.local_google_trial else {})}
    app.state.engine = engine
    app.state.session_factory = create_session_factory(engine)
    app.state.session_factory.configure(info={"source_wallet_enabled": resolved.source_wallet_enabled,
                                             "default_collection_access": resolved.source_wallet_enabled,
                                             "real_wallet_enabled": resolved.real_wallet_enabled,
                                             "wallet_requests_paused": resolved.wallet_requests_paused})
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
    app.add_middleware(DashboardGZipMiddleware)
    app.include_router(auth_router)
    app.include_router(admin_router)
    from .analysis_configuration import router as analysis_configuration_router
    app.include_router(analysis_configuration_router)
    app.include_router(registration_router)
    app.include_router(user_collection_router)
    from .analysis import router as analysis_router
    app.include_router(analysis_router)
    from .daily_routes import router as daily_router
    app.include_router(daily_router)
    app.include_router(router)
    web_root = web_root or Path(__file__).resolve().parents[3] / "web"
    if web_root.is_dir():
        app.mount("/", StaticFiles(directory=web_root, html=True), name="web")
    return app
