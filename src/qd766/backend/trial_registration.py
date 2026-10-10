"""Shared agency-only invitation. Pending accounts cannot read dashboard data."""
import secrets
import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Literal

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import select
from starlette.responses import JSONResponse

from .auth import SESSION_COOKIE, InviteToken, cookie_options, current_session, csrf_matches, digest
from .models import Department, Snapshot, SharedTrialLink, TrialRegistration, TrialInvitation, UserAccount

router = APIRouter(prefix="/api/v1", tags=["shared trial registration"])
LINK_COOKIE = "qd766_shared_invite"


def enabled(request):
    if not request.app.state.settings.shared_registration_enabled:
        raise HTTPException(503, "Đăng ký qua link chung chưa được mở.")


def valid_link(db, *, token=None, link_id=None, lock=False):
    query = select(SharedTrialLink).where(SharedTrialLink.token_hash == digest(token)) if token else select(SharedTrialLink).where(SharedTrialLink.id == link_id)
    if lock:
        query = query.with_for_update()
    link = db.scalar(query)
    if (link is None or link.revoked_at is not None or link.expires_at.replace(tzinfo=timezone.utc) <= datetime.now(timezone.utc)
            or link.registered_count >= link.max_registrations):
        return None
    return link


def applicant(request, db, *, write=False):
    session, account = current_session(db, request.cookies.get(SESSION_COOKIE))
    if account is None:
        raise HTTPException(401, "Vui lòng đăng nhập Google.")
    if write and not csrf_matches(request.headers.get("X-QD766-CSRF", ""), session.csrf_token):
        raise HTTPException(403, "Xác nhận phiên không hợp lệ.")
    registration = db.scalar(select(TrialRegistration).where(TrialRegistration.account_id == account.id).with_for_update() if write
                             else select(TrialRegistration).where(TrialRegistration.account_id == account.id))
    if registration is None and not account.trial_admitted:
        raise HTTPException(403, "Cần link đăng ký hợp lệ.")
    return session, account, registration


@router.post("/auth/registration-link")
def accept_link(payload: InviteToken, request: Request):
    enabled(request)
    with request.app.state.session_factory() as db:
        if valid_link(db, token=payload.token) is None:
            raise HTTPException(403, "Link đăng ký đã hết hạn, đã đủ số người hoặc đã thu hồi.")
    response = JSONResponse({"accepted": True})
    response.set_cookie(LINK_COOKIE, payload.token, max_age=600, **cookie_options(request.app.state.settings))
    return response


@router.get("/auth/registration")
def registration_status(request: Request):
    enabled(request)
    with request.app.state.session_factory() as db:
        session, account, item = applicant(request, db)
        return {"state": "approved" if account.trial_admitted else item.state, "name": account.display_name,
                "email": account.email, "csrfToken": session.csrf_token,
                "publicRegistration": bool(item and item.link_id is None),
                "provinceId": str(item.root_department_id) if item and item.root_department_id else None,
                "unitId": str(item.unit_department_id) if item and item.unit_department_id else None}


@router.get("/auth/registration/directory")
def registration_directory(request: Request, provinceId: uuid.UUID | None = None):
    enabled(request)
    from .admin import units_statement
    with request.app.state.session_factory() as db:
        _, account, _ = applicant(request, db)
        if account.trial_admitted:
            raise HTTPException(403, "Tài khoản đã được cấp quyền; sử dụng danh sách trong hệ thống.")
        roots = db.scalars(select(Department).join(Snapshot, Snapshot.root_department_id == Department.id)
                          .where(Snapshot.state == "complete", Snapshot.scope == "all").distinct().order_by(Department.name))
        units = db.scalars(units_statement(provinceId)) if provinceId else []
        return {"provinces": [{"id": str(d.id), "name": d.name} for d in roots],
                "units": [{"id": str(d.id), "name": d.name} for d in units]}


class AgencySelection(BaseModel):
    model_config = ConfigDict(extra="forbid")
    provinceId: uuid.UUID
    unitId: uuid.UUID


class PublicSelection(BaseModel):
    model_config = ConfigDict(extra="forbid")
    fullName: str = Field(min_length=2, max_length=160)
    birthDate: date
    gender: Literal["male", "female"]
    workplace: str = Field(default="", max_length=240)
    declarationAccepted: Literal[True]
    accessTier: Literal["agency"]
    provinceId: uuid.UUID
    unitId: uuid.UUID | None = None

    @field_validator("fullName", "workplace", mode="before")
    @classmethod
    def clean_text(cls, value):
        if not isinstance(value, str) or any(ord(c) < 32 for c in value):
            raise ValueError("Thông tin không hợp lệ.")
        return value.strip()

    @field_validator("birthDate")
    @classmethod
    def valid_birth(cls, value):
        if value > datetime.now(timezone(timedelta(hours=7))).date():
            raise ValueError("Ngày sinh không được ở tương lai.")
        return value


def validate_registration(db, province, unit, tier):
    from .admin import Assignment, validate_assignment
    validate_assignment(db, Assignment(provinceId=province, unitId=unit, accessTier=tier))


def validate_agency(db, payload):
    from .admin import Assignment, validate_assignment
    validate_assignment(db, Assignment(provinceId=payload.provinceId, unitId=payload.unitId, accessTier="agency"))


@router.post("/auth/registration")
def submit_registration(payload: AgencySelection, request: Request):
    enabled(request)
    with request.app.state.session_factory.begin() as db:
        _, account, item = applicant(request, db, write=True)
        if account.trial_admitted or item.state != "draft":
            raise HTTPException(409, "Yêu cầu đăng ký đã được gửi.")
        if item.link_id is None:
            raise HTTPException(422, "Vui lòng điền đầy đủ hồ sơ đăng ký tài khoản.")
        link = valid_link(db, link_id=item.link_id, lock=True)
        if link is None:
            raise HTTPException(403, "Link đăng ký đã hết hạn, đã đủ số người hoặc đã thu hồi.")
        validate_agency(db, payload)
        link.registered_count += 1
        item.state = "pending"
        item.root_department_id = payload.provinceId
        item.unit_department_id = payload.unitId
        item.submitted_at = datetime.now(timezone.utc)
    return {"state": "pending"}


@router.post("/auth/registration/public")
def submit_public_registration(payload: PublicSelection, request: Request):
    enabled(request)
    with request.app.state.session_factory.begin() as db:
        _, account, item = applicant(request, db, write=True)
        if account.trial_admitted or item is None or item.state != "draft":
            raise HTTPException(409, "Yêu cầu đăng ký đã được gửi.")
        if item.link_id is not None:
            raise HTTPException(403, "Đây là hồ sơ qua link mời; vui lòng gửi theo phạm vi được mời.")
        validate_registration(db, payload.provinceId, payload.unitId, payload.accessTier)
        item.full_name, item.birth_date, item.gender, item.workplace = payload.fullName, payload.birthDate, payload.gender, payload.workplace
        item.requested_tier = payload.accessTier
        item.root_department_id, item.unit_department_id = payload.provinceId, payload.unitId
        item.state = "pending"
        item.submitted_at = datetime.now(timezone.utc)
        account.display_name = payload.fullName
    return {"state": "pending", "message": "Đăng ký thành công. Hồ sơ của bạn đã được gửi đến quản trị viên để xét duyệt. Sau khi được duyệt, bạn có thể đăng nhập bằng tài khoản Google đã đăng ký."}


class LinkCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    days: int = Field(default=7, ge=1, le=30)
    maxRegistrations: int = Field(default=100, ge=1, le=1000)


@router.post("/admin/registration-links")
def create_link(payload: LinkCreate, request: Request):
    enabled(request)
    from .admin import administrator, audit
    with request.app.state.session_factory.begin() as db:
        actor = administrator(request, db, write=True)
        token = secrets.token_urlsafe(32)
        item = SharedTrialLink(token_hash=digest(token), created_by=actor.id, max_registrations=payload.maxRegistrations,
                               registered_count=0, expires_at=datetime.now(timezone.utc)+timedelta(days=payload.days))
        db.add(item); db.flush()
        audit(db, actor, "registration-link.created", linkId=str(item.id), maxRegistrations=item.max_registrations)
        return {"id": str(item.id), "token": token}


@router.get("/admin/registration-links")
def list_links(request: Request):
    enabled(request)
    from .admin import administrator
    with request.app.state.session_factory() as db:
        administrator(request, db)
        return [{"id": str(i.id), "expiresAt": i.expires_at.isoformat(), "registeredCount": i.registered_count,
                 "maxRegistrations": i.max_registrations, "revoked": i.revoked_at is not None}
                for i in db.scalars(select(SharedTrialLink).order_by(SharedTrialLink.created_at.desc()).limit(100))]


@router.post("/admin/registration-links/{link_id}/revoke")
def revoke_link(link_id: uuid.UUID, request: Request):
    enabled(request)
    from .admin import administrator, audit
    with request.app.state.session_factory.begin() as db:
        actor = administrator(request, db, write=True)
        item = db.get(SharedTrialLink, link_id)
        if item is None:
            raise HTTPException(404, "Không tìm thấy link.")
        item.revoked_at = datetime.now(timezone.utc)
        audit(db, actor, "registration-link.revoked", linkId=str(item.id))
    return {"revoked": True}


@router.get("/admin/registrations")
def list_registrations(request: Request):
    enabled(request)
    from .admin import administrator
    with request.app.state.session_factory() as db:
        administrator(request, db)
        rows = db.execute(select(TrialRegistration, UserAccount).join(UserAccount, TrialRegistration.account_id == UserAccount.id)
                          .where(TrialRegistration.state == "pending").order_by(TrialRegistration.submitted_at).limit(500)).all()
        return [{"id": str(i.id), "name": i.full_name or a.display_name, "email": a.email, "provinceId": str(i.root_department_id),
                 "unitId": str(i.unit_department_id) if i.unit_department_id else None, "province": db.get(Department, i.root_department_id).name,
                 "unit": db.get(Department, i.unit_department_id).name if i.unit_department_id else "Toàn tỉnh",
                 "accessTier": i.requested_tier, "birthDate": i.birth_date.isoformat() if i.birth_date else None,
                 "gender": i.gender, "workplace": i.workplace} for i, a in rows]


class RegistrationAssignment(BaseModel):
    model_config = ConfigDict(extra="forbid")
    provinceId: uuid.UUID
    unitId: uuid.UUID | None = None
    accessTier: Literal["province", "agency"] = "agency"


@router.post("/admin/registrations/{registration_id}/assignment")
def edit_registration(registration_id: uuid.UUID, payload: RegistrationAssignment, request: Request):
    enabled(request)
    from .admin import administrator, audit
    with request.app.state.session_factory.begin() as db:
        actor = administrator(request, db, write=True)
        item = db.scalar(select(TrialRegistration).where(TrialRegistration.id == registration_id).with_for_update())
        if item is None or item.state != "pending":
            raise HTTPException(409, "Yêu cầu không còn chờ duyệt.")
        if item.link_id is not None and payload.accessTier != "agency":
            raise HTTPException(422, "Link mời dùng chung chỉ cấp tài khoản cơ quan.")
        validate_registration(db, payload.provinceId, payload.unitId, payload.accessTier)
        item.root_department_id, item.unit_department_id = payload.provinceId, payload.unitId
        item.requested_tier = payload.accessTier
        audit(db, actor, "registration.assignment-updated", registrationId=str(item.id), **payload.model_dump(mode="json"))
    return {"updated": True}


class ReviewBatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ids: list[uuid.UUID] = Field(min_length=1, max_length=100)
    decision: Literal["approve", "reject"] = "approve"


@router.post("/admin/registrations/review")
def review_registrations(payload: ReviewBatch, request: Request):
    enabled(request)
    from .admin import administrator, audit
    from .invited_trial import activate_invited_trial
    with request.app.state.session_factory.begin() as db:
        actor = administrator(request, db, write=True)
        if payload.decision == "approve" and not db.info.get("source_wallet_enabled"):
            raise HTTPException(503, "Cần bật ví Credit trước khi duyệt dùng thử.")
        items = list(db.scalars(select(TrialRegistration).where(TrialRegistration.id.in_(sorted(set(payload.ids)))).order_by(TrialRegistration.id).with_for_update()))
        if len(items) != len(set(payload.ids)):
            raise HTTPException(404, "Không tìm thấy yêu cầu đăng ký.")
        count = 0
        for item in items:
            if item.state in {"approved", "rejected"}:
                continue  # A retry never grants another month/Credit.
            if item.state != "pending":
                raise HTTPException(409, "Yêu cầu chưa được gửi.")
            account = db.scalar(select(UserAccount).where(UserAccount.id == item.account_id).with_for_update())
            if not account.active or account.role != "user" or account.trial_admitted:
                raise HTTPException(409, "Tài khoản đã thay đổi; hãy tải lại danh sách.")
            now = datetime.now(timezone.utc)
            if payload.decision == "approve":
                if item.requested_tier not in {"province", "agency"}:
                    raise HTTPException(422, "Loại tài khoản không hợp lệ.")
                validate_registration(db, item.root_department_id, item.unit_department_id, item.requested_tier)
                account.access_tier = item.requested_tier
                account.root_department_id, account.unit_department_id = item.root_department_id, item.unit_department_id
                account.trial_admitted = True
                # Reviewed admission is represented by a redeemed one-time invitation.
                invitation = TrialInvitation(token_hash=digest(secrets.token_urlsafe(32)), created_by=actor.id,
                    recipient_email=account.email, root_department_id=item.root_department_id, unit_department_id=item.unit_department_id,
                    access_tier=item.requested_tier, expires_at=now+timedelta(days=1), used_at=now, used_by=account.id)
                db.add(invitation); db.flush()
                activate_invited_trial(db, account.id, invitation, now=now)
            item.state = "approved" if payload.decision == "approve" else "rejected"
            item.reviewed_at, item.reviewed_by = now, actor.id
            audit(db, actor, "registration."+item.state, registrationId=str(item.id), accountId=str(account.id))
            count += 1
    return {"reviewed": count}
