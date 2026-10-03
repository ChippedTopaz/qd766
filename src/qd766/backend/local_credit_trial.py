"""Explicit offline simulator. Never imported/registered by the production app factory."""
import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, ConfigDict
from sqlalchemy import delete, select
from starlette.responses import JSONResponse
from starlette.routing import Mount

from qd766.province_catalog import Province, ProvinceCatalog, ProvinceFormality
from qd766.province_roots import load_province_roots
from .admin import administrator
from .app import create_app
from .auth import SESSION_COOKIE, digest
from .config import Settings
from .importer import store_normalized_snapshot
from .jobs import halt_job, retry_or_fail_job, succeed_job
from .models import AccountCollectionPermission, Base, CollectionControl, CollectionJob, LoginSession, UserAccount
from .paid_requests import refund_blocked_paid_requests, refund_paid_requests_for_job, settle_paid_requests_for_job, top_up_credits

ROOT = load_province_roots()["25"].root_department_id
# Group identifiers must match the real application contract, not the labels below.
from .dashboard import GROUP_LABELS
GROUPS = dict(zip(GROUP_LABELS, (18, 20, 12, 22, 18, 10)))
ACCOUNTS = {"admin": "Quản trị mô phỏng", "a": "Người thử A", "b": "Người thử B",
            "agency": "Người thử cấp xã", "no-permission": "Người thử chưa có quyền TTHC"}


def identifier(value):
    return uuid.uuid5(uuid.NAMESPACE_URL, "qd766-local-credit-trial:" + value)


def mock_catalog():
    return ProvinceCatalog(Province("25", "Phú Thọ (mô phỏng)", "phu-tho"), "local-simulation", "0"*64, True, tuple(
        ProvinceFormality(str(identifier("formality:"+str(i))), f"TEST.00{i}", f"Thủ tục thử nghiệm {i} — dữ liệu mô phỏng",
            "Lĩnh vực mô phỏng", "Cơ quan mô phỏng", levels, "external", "active", False)
        for i, levels in ((1, ("province", "ward")), (2, ("province",)), (3, ("ward",)))))


def mock_snapshot(request_value=None):
    selection = request_value or {"period": {"type": "year", "year": 2026}, "scope": "all", "formalityId": None}
    period, scope, formality = selection["period"], selection["scope"], selection.get("formalityId")
    def entity(id, name, maximum, level, ratio):
        return {"departmentId": str(id), "departmentName": name, "departmentCode": "H44",
            "departmentType": level, "departmentLevel": level, "apiScore": round(maximum*ratio, 2),
            "apiMaxScore": maximum, "apiRatio": ratio*100, "scoreSource": "local-simulation",
            "parameters": {}, "metrics": [{"code": "SIMULATED", "name": "Chỉ tiêu mô phỏng — không phải số liệu thực",
                "numerator": 70, "denominator": 100, "ratio": 70, "apiScore": round(maximum*ratio, 2),
                "apiMaxScore": maximum, "extras": {}}]}
    datasets=[]
    for group, maximum in GROUPS.items():
        sha=hashlib.sha256(f"local:{group}:{period}:{scope}:{formality}".encode()).hexdigest()
        datasets.append({"group": group, "schemaKind": "metrics", "formulaStatus": "simulation-only",
            "scorePolicy": "api-authoritative", "root": entity(ROOT, "UBND tỉnh Phú Thọ (mô phỏng)", maximum, "PROVINCE", .7),
            "children": [entity(identifier("department:agency"), "Sở mô phỏng", maximum, "PROVINCE", .75),
                         entity(identifier("department:commune"), "UBND xã mô phỏng", maximum, "COMMUNE", .65)],
            "period": period, "scope": scope, "formalityId": formality,
            "raw": {"path": "local-simulation/"+group, "sha256": sha}})
    return {"schemaVersion": 1, "period": period, "scope": scope, "formalityId": formality,
        "status": {"state": "complete", "requiredGroups": list(GROUPS), "loadedGroups": list(GROUPS),
                   "missingGroups": [], "unsupportedGroups": []}, "datasets": datasets,
        "provinceAggregatedScore": 70, "provinceAggregatedMaximum": 100,
        "scorePolicy": {"authoritativeValue": "apiScore", "simulation": True}}


def create_local_credit_trial(database_url: str, web_root: Path | None = None):
    if not database_url.startswith("sqlite+pysqlite://"):
        raise ValueError("Local credit simulator only accepts an isolated SQLite database")
    app=create_app(Settings(database_url=database_url, public_read_only=True, require_login=True, invite_required=True,
        paid_requests_enabled=True, formality_credit_cost=3, trial_credits_enabled=True, trial_credit_management=True,
        google_client_id="local-simulation-not-google", google_client_secret=secrets.token_urlsafe(32),
        google_redirect_uri="https://127.0.0.1/api/v1/auth/google/callback"), web_root=web_root)
    app.state.local_credit_trial=True
    # No external provider, worker or real catalog client is used by this simulator.
    class MockCatalogClient:
        def load(self, *args, **kwargs):
            return mock_catalog()
    app.state.province_catalog_client=MockCatalogClient()
    Base.metadata.create_all(app.state.engine)
    with app.state.session_factory.begin() as db:
        if db.scalar(select(UserAccount.id).where(~UserAccount.external_subject.like("local-trial:%")).limit(1)):
            raise ValueError("Refusing database containing non-simulation identities")
        store_normalized_snapshot(db, mock_snapshot())
        for key, name in ACCOUNTS.items():
            if db.get(UserAccount, identifier("account:"+key)) is not None:
                continue
            account=UserAccount(id=identifier("account:"+key), external_subject="local-trial:"+key, display_name=name,
                role="admin" if key=="admin" else "user", plan="free", active=True, trial_admitted=True,
                root_department_id=ROOT, access_tier="agency" if key=="agency" else "province",
                unit_department_id=identifier("department:commune") if key=="agency" else None)
            db.add(account);db.flush()
            db.add(AccountCollectionPermission(account_id=account.id, enabled=key!="no-permission"))
            top_up_credits(db, account.id, 30, event_key="simulation-seed:"+key, details={"simulation": True})
    router=APIRouter(prefix="/api/v1/local-trial")

    class Login(BaseModel):
        model_config=ConfigDict(extra="forbid")
        account: Literal["admin", "a", "b", "agency", "no-permission"]

    class Outcome(BaseModel):
        model_config=ConfigDict(extra="forbid")
        action: Literal["success", "failure", "cancel", "circuit-open", "circuit-close"]
        jobId: uuid.UUID | None = None

    @router.get("/accounts")
    def available_accounts():
        return {"simulation": True, "creditCost": 3, "accounts": [{"key": k, "name": v} for k,v in ACCOUNTS.items()]}

    @router.post("/login")
    def local_login(payload: Login, request: Request):
        with app.state.session_factory.begin() as db:
            account=db.get(UserAccount, identifier("account:"+payload.account))
            if not account.active:
                raise HTTPException(403,"Tài khoản mô phỏng đã khóa.")
            old=request.cookies.get(SESSION_COOKIE)
            if old:db.execute(delete(LoginSession).where(LoginSession.token_hash==digest(old)))
            token=secrets.token_urlsafe(32)
            db.add(LoginSession(token_hash=digest(token), account_id=account.id, csrf_token=secrets.token_urlsafe(32),
                expires_at=datetime.now(timezone.utc)+timedelta(hours=8)))
        response=JSONResponse({"loggedIn": True, "simulation": True})
        response.set_cookie(SESSION_COOKIE, token, max_age=28800, httponly=True, secure=False, samesite="strict", path="/")
        return response

    @router.get("/jobs")
    def jobs(request: Request):
        with app.state.session_factory() as db:
            administrator(request, db)
            return [{"id":str(job.id),"state":job.state,"formalityId":job.request.get("formalityId")}
                for job in db.scalars(select(CollectionJob).order_by(CollectionJob.created_at.desc()).limit(100))]

    @router.post("/outcome")
    def apply_outcome(payload: Outcome, request: Request):
        with app.state.session_factory.begin() as db:
            administrator(request, db, write=True)
            if payload.action.startswith("circuit-"):
                control=db.get(CollectionControl,"dvcqg")
                if control is None:
                    control=CollectionControl(key="dvcqg");db.add(control)
                control.circuit_state="open" if payload.action=="circuit-open" else "closed"
                db.flush()
                if control.circuit_state=="open":refund_blocked_paid_requests(db)
            else:
                job=db.get(CollectionJob,payload.jobId) if payload.jobId else None
                if job is None:raise HTTPException(404,"Chọn job mô phỏng.")
                if job.state not in {"queued","running"}:raise HTTPException(409,"Job đã kết thúc.")
                job.state="running";job.locked_by="local-simulation";job.attempts+=1
                db.flush()
                if payload.action=="success":
                    snapshot=store_normalized_snapshot(db,mock_snapshot(job.request))
                    settle_paid_requests_for_job(db,job,snapshot)
                    succeed_job(db,job,"local-simulation")
                else:
                    error={"kind":"simulation-"+payload.action,"retryable":False}
                    if payload.action=="cancel":halt_job(db,job,"local-simulation",error)
                    else:retry_or_fail_job(db,job,"local-simulation",error)
                    refund_paid_requests_for_job(db,job,error)
        app.state.dashboard_cache.clear()
        return {"simulated": payload.action}
    app.include_router(router)
    # create_app mounts static files last; appended simulator routes must precede that catch-all.
    app.router.routes[:] = [route for route in app.router.routes if not isinstance(route, Mount)] + [
        route for route in app.router.routes if isinstance(route, Mount)]

    @app.middleware("http")
    async def loopback_only(request, call_next):
        host=request.url.hostname
        if host not in {"127.0.0.1","localhost"} or request.client.host not in {"127.0.0.1","::1"}:
            return JSONResponse({"detail":"Local simulator is loopback-only"},status_code=403)
        origin=request.headers.get("origin")
        if origin and origin!=str(request.base_url).rstrip("/"):
            return JSONResponse({"detail":"Cross-origin request denied"},status_code=403)
        if request.url.path in {"/api/v1/auth/google/start","/api/v1/auth/google/callback","/api/v1/auth/invite"}:
            return JSONResponse({"detail":"Google/invites are not used by this offline simulator"},status_code=403)
        response=await call_next(request)
        response.headers["Cache-Control"]="no-store"
        response.headers["X-QD766-Local-Simulation"]="true"
        return response
    return app
