"""Google authorization-code login. Google tokens are verified then discarded."""
import base64
import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode, urlsplit

import httpx
from fastapi import APIRouter, HTTPException, Request
from sqlalchemy import delete, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from starlette.responses import RedirectResponse

from .models import LoginAttempt, LoginSession, UserAccount

router = APIRouter(prefix="/api/v1/auth", tags=["authentication"])
SESSION_COOKIE = "qd766_session"
FLOW_COOKIE = "qd766_login_flow"
SESSION_SECONDS = 8 * 3600


def digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def enabled(settings) -> bool:
    return bool(settings.google_client_id and settings.google_client_secret and settings.google_redirect_uri)


def validate_auth_settings(settings):
    values = (settings.google_client_id, settings.google_client_secret, settings.google_redirect_uri)
    if any(values) and not all(values):
        raise ValueError("Google login requires client ID, secret and redirect URI together")
    if settings.require_login and (not enabled(settings) or not settings.public_read_only):
        raise ValueError("Login-required instance must enable public read-only boundary and configure Google")
    if enabled(settings):
        uri = urlsplit(settings.google_redirect_uri)
        local = uri.hostname in {"127.0.0.1", "localhost"}
        if uri.username or uri.password or uri.query or uri.fragment or uri.path != "/api/v1/auth/google/callback" or not uri.netloc:
            raise ValueError("Invalid Google redirect URI")
        if uri.scheme != "https" and not (uri.scheme == "http" and local and not settings.public_read_only):
            raise ValueError("Public Google login requires HTTPS")


def cookie_options(settings) -> dict:
    return {"httponly": True, "secure": urlsplit(settings.google_redirect_uri).scheme == "https", "samesite": "lax", "path": "/"}


def current_session(db, token: str | None):
    if not token or len(token) > 200:
        return None, None
    session = db.get(LoginSession, digest(token))
    now = datetime.now(timezone.utc)
    if session is None or session.expires_at.replace(tzinfo=timezone.utc) <= now:
        return None, None
    account = db.get(UserAccount, session.account_id)
    if account is None or not account.active:
        return None, None
    return session, account


def verify_google_identity(code: str, verifier: str, nonce: str, settings) -> dict:
    # Import lazily so an unconfigured office server has no Google/network dependency.
    from google.auth.transport.requests import Request as GoogleRequest
    from google.oauth2.id_token import verify_oauth2_token
    import requests

    with httpx.Client(timeout=15, follow_redirects=False) as client:
        response = client.post("https://oauth2.googleapis.com/token", data={
            "code": code, "client_id": settings.google_client_id,
            "client_secret": settings.google_client_secret,
            "redirect_uri": settings.google_redirect_uri,
            "grant_type": "authorization_code", "code_verifier": verifier,
        })
        response.raise_for_status()
        token = response.json().get("id_token")
    if not isinstance(token, str):
        raise ValueError("No ID token")
    class BoundedGoogleRequest(GoogleRequest):
        def __call__(self, *args, **kwargs):
            kwargs["timeout"] = 15
            return super().__call__(*args, **kwargs)
    with requests.Session() as transport:
        identity = verify_oauth2_token(token, BoundedGoogleRequest(session=transport), audience=settings.google_client_id)
    return validate_google_claims(identity, nonce, settings.google_client_id)


def validate_google_claims(identity: dict, nonce: str, audience: str) -> dict:
    if (identity.get("iss") not in {"https://accounts.google.com", "accounts.google.com"}
            or not secrets.compare_digest(str(identity.get("nonce", "")), nonce)
            or identity.get("email_verified") is not True
            or not isinstance(identity.get("sub"), str) or not identity["sub"] or len(identity["sub"]) > 200
            or not isinstance(identity.get("email"), str) or len(identity["email"]) > 320
            or identity.get("aud") != audience):
        raise ValueError("Invalid Google identity")
    return identity


@router.get("/google/start")
def google_start(request: Request):
    settings = request.app.state.settings
    if not enabled(settings):
        raise HTTPException(503, "Đăng nhập Google chưa được cấu hình.")
    state, binding, nonce, verifier = [secrets.token_urlsafe(32) for _ in range(4)]
    now = datetime.now(timezone.utc)
    with request.app.state.session_factory.begin() as db:
        db.execute(delete(LoginAttempt).where(LoginAttempt.expires_at <= now))
        db.add(LoginAttempt(state_hash=digest(state), binding_hash=digest(binding), nonce=nonce, verifier=verifier, expires_at=now + timedelta(minutes=10)))
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip("=")
    params = {"client_id": settings.google_client_id, "redirect_uri": settings.google_redirect_uri,
              "response_type": "code", "scope": "openid email profile", "state": state, "nonce": nonce,
              "code_challenge": challenge, "code_challenge_method": "S256", "prompt": "select_account"}
    response = RedirectResponse("https://accounts.google.com/o/oauth2/v2/auth?" + urlencode(params), status_code=303)
    response.set_cookie(FLOW_COOKIE, binding, max_age=600, **cookie_options(settings))
    response.headers["Cache-Control"] = "no-store"
    return response


@router.get("/google/callback")
def google_callback(request: Request, state: str = "", code: str = "", error: str = ""):
    settings = request.app.state.settings
    if not enabled(settings):
        raise HTTPException(503, "Đăng nhập Google chưa được cấu hình.")
    now = datetime.now(timezone.utc)
    attempt = None
    binding = request.cookies.get(FLOW_COOKIE, "")
    if state and binding and len(state) <= 200 and len(binding) <= 200:
        with request.app.state.session_factory.begin() as db:
            # Atomic one-time claim prevents replay, including two concurrent callbacks.
            attempt = db.scalar(update(LoginAttempt).where(
                LoginAttempt.state_hash == digest(state), LoginAttempt.binding_hash == digest(binding),
                LoginAttempt.consumed_at.is_(None), LoginAttempt.expires_at > now,
            ).values(consumed_at=now).returning(LoginAttempt))
    response = RedirectResponse("/?login=failed", status_code=303)
    response.delete_cookie(FLOW_COOKIE, **cookie_options(settings))
    response.headers["Cache-Control"] = "no-store"
    if attempt is None or not code or len(code) > 4096 or error:
        return response
    try:
        identity = verify_google_identity(code, attempt.verifier, attempt.nonce, settings)
    except Exception:
        # Never return/log token, authorization code, secret or Google's error body.
        return response
    with request.app.state.session_factory.begin() as db:
        subject = "google:" + identity["sub"]
        insert = sqlite_insert if db.bind.dialect.name == "sqlite" else pg_insert
        db.execute(insert(UserAccount).values(external_subject=subject,
            display_name=str(identity.get("name") or identity["email"])[:160], email=identity["email"],
            plan="free", credit_balance=0, credit_reserved=0, active=True).on_conflict_do_nothing(index_elements=["external_subject"]))
        account = db.scalar(select(UserAccount).where(UserAccount.external_subject == subject).with_for_update())
        if account is None or not account.active:
            return response
        account.email = identity["email"]
        account.display_name = str(identity.get("name") or identity["email"])[:160]
        old = request.cookies.get(SESSION_COOKIE)
        if old:
            db.execute(delete(LoginSession).where(LoginSession.token_hash == digest(old)))
        db.execute(delete(LoginSession).where(LoginSession.expires_at <= now))
        token = secrets.token_urlsafe(32)
        db.add(LoginSession(token_hash=digest(token), account_id=account.id, csrf_token=secrets.token_urlsafe(32), expires_at=now + timedelta(seconds=SESSION_SECONDS)))
    response = RedirectResponse("/", status_code=303)
    response.set_cookie(SESSION_COOKIE, token, max_age=SESSION_SECONDS, **cookie_options(settings))
    response.delete_cookie(FLOW_COOKIE, **cookie_options(settings))
    response.headers["Cache-Control"] = "no-store"
    return response


@router.get("/me")
def me(request: Request):
    with request.app.state.session_factory() as db:
        session, account = current_session(db, request.cookies.get(SESSION_COOKIE)) if request.cookies.get(SESSION_COOKIE) else (None, None)
        if not account:
            raise HTTPException(401, "Chưa đăng nhập.")
        return {"id": str(account.id), "name": account.display_name, "email": account.email,
                "plan": account.plan, "provinceId": str(account.root_department_id) if account.root_department_id else None,
                "credits": account.credit_balance, "csrfToken": session.csrf_token}


@router.post("/logout")
def logout(request: Request):
    with request.app.state.session_factory.begin() as db:
        session, account = current_session(db, request.cookies.get(SESSION_COOKIE))
        if session and not secrets.compare_digest(request.headers.get("X-QD766-CSRF", ""), session.csrf_token):
            raise HTTPException(403, "Xác nhận phiên không hợp lệ.")
        if session:
            db.delete(session)
    response = RedirectResponse("/", status_code=303)
    response.delete_cookie(SESSION_COOKIE, **cookie_options(request.app.state.settings))
    return response
