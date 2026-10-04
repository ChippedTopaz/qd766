"""Google authorization-code login. Google tokens are verified then discarded."""
import base64
import hashlib
import secrets
import logging
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode, urlsplit

import httpx
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import delete, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from starlette.responses import RedirectResponse, JSONResponse

from .models import AdminAudit, LoginAttempt, LoginSession, TrialInvitation, UserAccount

router = APIRouter(prefix="/api/v1/auth", tags=["authentication"])
SESSION_COOKIE = "qd766_session"
FLOW_COOKIE = "qd766_login_flow"
INVITE_COOKIE = "qd766_invite"
SESSION_SECONDS = 8 * 3600


def digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def enabled(settings) -> bool:
    return bool(settings.google_client_id and settings.google_client_secret and settings.google_redirect_uri)


def validate_auth_settings(settings):
    if settings.local_google_trial:
        from sqlalchemy.engine import make_url
        database = make_url(settings.database_url)
        if (settings.google_redirect_uri != "http://127.0.0.1:8771/api/v1/auth/google/callback"
                or database.drivername != "postgresql+psycopg"
                or database.host not in {"127.0.0.1", "localhost", "::1"}
                or database.database != "qd766_credit_test"
                or not settings.require_login or not settings.public_read_only):
            raise ValueError("Local Google trial requires fixed loopback callback and isolated test database")
    values = (settings.google_client_id, settings.google_client_secret, settings.google_redirect_uri)
    if any(values) and not all(values):
        raise ValueError("Google login requires client ID, secret and redirect URI together")
    if settings.require_login and (not enabled(settings) or not settings.public_read_only):
        raise ValueError("Login-required instance must enable public read-only boundary and configure Google")
    if settings.invite_required and not settings.require_login:
        raise ValueError("Invite-only deployment requires authenticated access")
    if enabled(settings):
        uri = urlsplit(settings.google_redirect_uri)
        local = uri.hostname in {"127.0.0.1", "localhost"}
        if uri.username or uri.password or uri.query or uri.fragment or uri.path != "/api/v1/auth/google/callback" or not uri.netloc:
            raise ValueError("Invalid Google redirect URI")
        if uri.scheme != "https" and not (uri.scheme == "http" and local and (not settings.public_read_only or settings.local_google_trial)):
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


class InviteToken(BaseModel):
    token: str = Field(min_length=40, max_length=100)


@router.post("/invite")
def accept_invite(payload: InviteToken, request: Request):
    # The frontend reads a URL fragment: the invitation token is never in HTTP URLs.
    now = datetime.now(timezone.utc)
    with request.app.state.session_factory() as db:
        invitation = db.scalar(select(TrialInvitation).where(
            TrialInvitation.token_hash == digest(payload.token), TrialInvitation.used_at.is_(None),
            TrialInvitation.revoked_at.is_(None), TrialInvitation.expires_at > now))
        if invitation is None:
            raise HTTPException(403, "Lời mời đã hết hạn, đã dùng hoặc đã được thu hồi.")
    response = JSONResponse({"accepted": True})
    response.set_cookie(INVITE_COOKIE, payload.token, max_age=600, **cookie_options(request.app.state.settings))
    response.headers["Cache-Control"] = "no-store"
    return response


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
        invitation = None
        invite_token = request.cookies.get(INVITE_COOKIE, "")
        if 40 <= len(invite_token) <= 100:
            invitation = db.scalar(select(TrialInvitation.id).where(TrialInvitation.token_hash == digest(invite_token),
                TrialInvitation.used_at.is_(None), TrialInvitation.revoked_at.is_(None), TrialInvitation.expires_at > now))
        db.add(LoginAttempt(state_hash=digest(state), binding_hash=digest(binding), nonce=nonce, verifier=verifier,
            invitation_id=invitation, expires_at=now + timedelta(minutes=10)))
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
    except Exception as failure:
        # Never return/log token, authorization code, secret or Google's error body.
        if settings.local_google_trial:
            status = failure.response.status_code if isinstance(failure, httpx.HTTPStatusError) else None
            reason = "unspecified"
            if isinstance(failure, httpx.HTTPStatusError):
                try:
                    value = failure.response.json().get("error")
                    if value in {"invalid_client", "invalid_grant", "redirect_uri_mismatch", "unauthorized_client", "invalid_request"}:
                        reason = value
                except (ValueError, AttributeError, TypeError):
                    pass
            logging.getLogger("uvicorn.error").warning(
                "LOCAL_GOOGLE_LOGIN_FAILED type=%s status=%s reason=%s",
                type(failure).__name__, status, reason)
        return response
    with request.app.state.session_factory.begin() as db:
        subject = "google:" + identity["sub"]
        existing = db.scalar(select(UserAccount).where(UserAccount.external_subject == subject).with_for_update())
        if existing is not None and not existing.active:
            return response
        needs_invite = settings.invite_required and (existing is None or not existing.trial_admitted)
        invitation = None
        if needs_invite:
            # Atomic one-use claim; rolls back with account/session creation on errors.
            invitation = db.scalar(update(TrialInvitation).where(TrialInvitation.id == attempt.invitation_id,
                TrialInvitation.used_at.is_(None), TrialInvitation.revoked_at.is_(None), TrialInvitation.expires_at > now,
                (TrialInvitation.recipient_email.is_(None) | (TrialInvitation.recipient_email == identity["email"].lower()))
            ).values(used_at=now).returning(TrialInvitation))
            if invitation is None:
                response.headers["location"] = "/?login=invite-required"
                return response
        insert = sqlite_insert if db.bind.dialect.name == "sqlite" else pg_insert
        db.execute(insert(UserAccount).values(external_subject=subject,
            display_name=str(identity.get("name") or identity["email"])[:160], email=identity["email"],
            plan="free", credit_balance=0, credit_reserved=0, active=True).on_conflict_do_nothing(index_elements=["external_subject"]))
        account = db.scalar(select(UserAccount).where(UserAccount.external_subject == subject).with_for_update())
        if account is None or not account.active:
            return response
        account.email = identity["email"]
        account.display_name = str(identity.get("name") or identity["email"])[:160]
        if invitation is not None:
            account.trial_admitted = True
            account.root_department_id = invitation.root_department_id
            account.access_tier = invitation.access_tier
            account.unit_department_id = invitation.unit_department_id
            invitation.used_by = account.id
            db.flush()
            if settings.source_wallet_enabled:
                from .invited_trial import activate_invited_trial
                activate_invited_trial(db,account.id,invitation,now=now)
            db.add(AdminAudit(actor_id=invitation.created_by, action="invitation.redeemed",
                details={"invitationId": str(invitation.id), "accountId": str(account.id)}))
        old = request.cookies.get(SESSION_COOKIE)
        if old:
            db.execute(delete(LoginSession).where(LoginSession.token_hash == digest(old)))
        db.execute(delete(LoginSession).where(LoginSession.expires_at <= now))
        token = secrets.token_urlsafe(32)
        db.add(LoginSession(token_hash=digest(token), account_id=account.id, csrf_token=secrets.token_urlsafe(32), expires_at=now + timedelta(seconds=SESSION_SECONDS)))
    response = RedirectResponse("/", status_code=303)
    response.set_cookie(SESSION_COOKIE, token, max_age=SESSION_SECONDS, **cookie_options(settings))
    response.delete_cookie(FLOW_COOKIE, **cookie_options(settings))
    response.delete_cookie(INVITE_COOKIE, **cookie_options(settings))
    response.headers["Cache-Control"] = "no-store"
    return response


@router.get("/me")
def me(request: Request):
    with request.app.state.session_factory() as db:
        session, account = current_session(db, request.cookies.get(SESSION_COOKIE)) if request.cookies.get(SESSION_COOKIE) else (None, None)
        if not account:
            raise HTTPException(401, "Chưa đăng nhập.")
        if request.app.state.settings.invite_required and not account.trial_admitted:
            raise HTTPException(403, "Tài khoản chưa được mời dùng thử.")
        from .collection_permissions import can_collect
        collection_allowed = request.app.state.settings.paid_requests_enabled and can_collect(db, account.id)
        from .wallet_access import credits
        available,reserved=credits(db,account)
        return {"id": str(account.id), "name": account.display_name, "email": account.email,
                "plan": account.plan, "provinceId": str(account.root_department_id) if account.root_department_id else None,
                "credits": available, "csrfToken": session.csrf_token,
                "role": account.role, "accessTier": account.access_tier, "canCollect": collection_allowed,
                "reservedCredits": reserved,
                "unitId": str(account.unit_department_id) if account.unit_department_id else None}


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
