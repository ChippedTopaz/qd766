"""Authenticated trial administration. No collection/circuit or billing controls."""
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Literal

from fastapi import APIRouter, HTTPException, Request, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import delete, select

from .auth import SESSION_COOKIE, current_session, digest, csrf_matches
from .models import AccountCollectionPermission, AdminAudit, CreditLedgerEntry, Department, Dataset, Entity, LoginSession, Snapshot, TrialInvitation, UserAccount, SubscriptionCycle
from .wallet_access import enabled as wallet_enabled, credits, active_subscription, subscription_summary

router = APIRouter(prefix="/api/v1/admin", tags=["trial administration"])

@router.get('/collection-log')
def collection_log(request: Request, kind: Literal['default','formality'] | None = None,
                   source: Literal['system','user'] | None = None,
                   state: Literal['queued','running','succeeded','failed','halted'] | None = None,
                   offset: int = Query(0,ge=0,le=100000), limit: int = Query(30,ge=1,le=100)):
    from .collection_monitor import collection_status, probe_status, daily_status
    with request.app.state.session_factory() as db:
        administrator(request,db)
        report=collection_status(db,kind=kind,source=source,state=state,offset=offset,limit=limit)
    report['localSimulation']=bool(request.app.state.settings.local_google_trial)
    report['probe']=None if source=='user' else probe_status(getattr(request.app.state,'collection_probe_checkpoint',None))
    report['daily']=[] if source=='user' else daily_status()
    return report


def administrator(request, db, *, write=False):
    session, account = current_session(db, request.cookies.get(SESSION_COOKIE))
    if account is None:
        raise HTTPException(401, "Vui lòng đăng nhập.")
    if account.role != "admin" or not account.trial_admitted:
        raise HTTPException(403, "Chỉ tài khoản quản trị được sử dụng chức năng này.")
    if write and not csrf_matches(request.headers.get("X-QD766-CSRF", ""), session.csrf_token):
        raise HTTPException(403, "Xác nhận phiên không hợp lệ.")
    return account


def units_statement(root):
    return select(Department).join(Entity, Entity.department_id == Department.id).join(Dataset).join(Snapshot).where(
        Snapshot.root_department_id == root, Snapshot.scope == "all", Snapshot.state == "complete",
        Entity.entity_kind == "child", Department.id != root).distinct().order_by(Department.name)


class Assignment(BaseModel):
    model_config = ConfigDict(extra="forbid")
    provinceId: uuid.UUID
    accessTier: Literal["province", "agency", "national"] = "province"
    unitId: uuid.UUID | None = None


def validate_assignment(db, payload):
    # Province identity must be an actual stored snapshot root, not a client-supplied label.
    if db.scalar(select(Snapshot.id).where(Snapshot.root_department_id == payload.provinceId,
            Snapshot.state == "complete", Snapshot.scope == "all").limit(1)) is None:
        raise HTTPException(422, "Tỉnh chưa có dữ liệu chi tiết trong hệ thống.")
    if payload.accessTier == "agency":
        if payload.unitId is None or db.scalar(units_statement(payload.provinceId).where(Department.id == payload.unitId)) is None:
            raise HTTPException(422, "Cơ quan không thuộc tỉnh đã chọn.")
    elif payload.unitId is not None:
        raise HTTPException(422, "Quyền cả tỉnh không gán cơ quan riêng.")


class InviteCreate(Assignment):
    email: str | None = Field(default=None, max_length=320)
    days: int = Field(default=7, ge=1, le=30)


class AccountChange(Assignment):
    active: bool


def audit(db, actor, action, **details):
    db.add(AdminAudit(actor_id=actor.id, action=action, details=details))


@router.get("/directory")
def directory(request: Request, provinceId: uuid.UUID | None = None):
    with request.app.state.session_factory() as db:
        administrator(request, db)
        roots = list(db.scalars(select(Department).join(Snapshot, Snapshot.root_department_id == Department.id)
            .where(Snapshot.state == "complete", Snapshot.scope == "all").distinct().order_by(Department.name)))
        units = list(db.scalars(units_statement(provinceId))) if provinceId else []
        return {"provinces": [{"id": str(d.id), "name": d.name} for d in roots],
                "units": [{"id": str(d.id), "name": d.name} for d in units]}


@router.get("/accounts")
def accounts(request: Request):
    with request.app.state.session_factory() as db:
        administrator(request, db)
        from .admin_accounts import account_projections
        users = list(db.scalars(select(UserAccount).order_by(UserAccount.created_at.desc()).limit(500)))
        department_ids = {value for a in users for value in (a.root_department_id, a.unit_department_id) if value}
        names = dict(db.execute(select(Department.id, Department.name).where(Department.id.in_(department_ids))).all())
        projections = account_projections(db, users)
        return [{"id": str(a.id), "email": a.email, "name": a.display_name, "role": a.role,
                 "admitted": a.trial_admitted, "active": a.active, "accessTier": a.access_tier,
                 **projections[a.id],
                 "canCollect": bool(request.app.state.settings.paid_requests_enabled and projections[a.id]["canCollect"]),
                 "provinceId": str(a.root_department_id) if a.root_department_id else None,
                 "provinceName": names.get(a.root_department_id),
                 "unitName": names.get(a.unit_department_id),
                 "unitId": str(a.unit_department_id) if a.unit_department_id else None}
                for a in users]


@router.post("/accounts/{account_id}")
def change_account(account_id: uuid.UUID, payload: AccountChange, request: Request):
    with request.app.state.session_factory.begin() as db:
        actor = administrator(request, db, write=True)
        target = db.scalar(select(UserAccount).where(UserAccount.id == account_id).with_for_update())
        if target is None:
            raise HTTPException(404, "Không tìm thấy tài khoản.")
        if target.role == "admin":
            raise HTTPException(403, "Không chỉnh sửa tài khoản quản trị ở màn hình này.")
        validate_assignment(db, payload)
        before = {"active": target.active, "provinceId": str(target.root_department_id),
                  "accessTier": target.access_tier, "unitId": str(target.unit_department_id)}
        target.active = payload.active
        target.root_department_id = payload.provinceId
        target.access_tier = payload.accessTier
        target.unit_department_id = payload.unitId
        # Changing scope is not an alternative route to admission without an invite.
        db.execute(delete(LoginSession).where(LoginSession.account_id == target.id))
        audit(db, actor, "account.updated", accountId=str(target.id), before=before, after=payload.model_dump(mode="json"))
    return {"updated": True, "sessionsRevoked": True}


@router.post("/invitations")
def create_invitation(payload: InviteCreate, request: Request):
    with request.app.state.session_factory.begin() as db:
        actor = administrator(request, db, write=True)
        validate_assignment(db, payload)
        email = (payload.email or "").strip().lower() or None
        if email and ("@" not in email or any(c.isspace() for c in email)):
            raise HTTPException(422, "Email không hợp lệ.")
        token = secrets.token_urlsafe(32)
        invitation = TrialInvitation(token_hash=digest(token), created_by=actor.id, recipient_email=email,
            root_department_id=payload.provinceId, access_tier=payload.accessTier, unit_department_id=payload.unitId,
            expires_at=datetime.now(timezone.utc) + timedelta(days=payload.days))
        db.add(invitation)
        db.flush()
        audit(db, actor, "invitation.created", invitationId=str(invitation.id), email=email,
              provinceId=str(payload.provinceId), accessTier=payload.accessTier, unitId=str(payload.unitId))
        return {"id": str(invitation.id), "token": token, "expiresAt": invitation.expires_at.isoformat()}


@router.get("/invitations")
def invitations(request: Request):
    with request.app.state.session_factory() as db:
        administrator(request, db)
        now = datetime.now(timezone.utc)
        return [{"id": str(i.id), "email": i.recipient_email, "expiresAt": i.expires_at.isoformat(),
                 "state": "used" if i.used_at else "revoked" if i.revoked_at else "expired" if i.expires_at.replace(tzinfo=timezone.utc) <= now else "available"}
                for i in db.scalars(select(TrialInvitation).order_by(TrialInvitation.created_at.desc()).limit(200))]


@router.post("/invitations/{invitation_id}/revoke")
def revoke(invitation_id: uuid.UUID, request: Request):
    with request.app.state.session_factory.begin() as db:
        actor = administrator(request, db, write=True)
        invitation = db.scalar(select(TrialInvitation).where(TrialInvitation.id == invitation_id).with_for_update())
        if invitation is None:
            raise HTTPException(404, "Không tìm thấy lời mời.")
        if invitation.used_at:
            raise HTTPException(409, "Lời mời đã dùng; hãy khóa tài khoản nếu cần.")
        invitation.revoked_at = datetime.now(timezone.utc)
        audit(db, actor, "invitation.revoked", invitationId=str(invitation_id))
    return {"revoked": True}


@router.get("/audit")
def audit_log(request: Request):
    with request.app.state.session_factory() as db:
        administrator(request, db)
        return [{"action": a.action, "details": a.details, "at": a.created_at.isoformat()}
                for a in db.scalars(select(AdminAudit).order_by(AdminAudit.created_at.desc()).limit(100))]


class TrialCreditChange(BaseModel):
    model_config = ConfigDict(extra="forbid")
    operationId: uuid.UUID
    canCollect: bool = True
    amount: int = Field(default=0, ge=0, le=100000)
    reason: str = Field(min_length=3, max_length=240)
    creditSource: Literal["subscription", "purchased"] | None = None


class TrialActivation(BaseModel):
    model_config=ConfigDict(extra="forbid")
    operationId:uuid.UUID


@router.post("/accounts/{account_id}/trial-activation")
def activate_trial(account_id:uuid.UUID,payload:TrialActivation,request:Request):
    if not request.app.state.settings.source_wallet_enabled:
        raise HTTPException(403,"Kích hoạt subscription chưa được mở ở môi trường này.")
    from .paid_requests import _locked_account
    from .wallet_access import enroll
    from .subscriptions import schedule_plan,grant_due_cycles
    from .credit_wallet import WalletError,utc
    with request.app.state.session_factory.begin() as db:
        actor=administrator(request,db,write=True)
        if db.get(UserAccount,account_id) is None:
            raise HTTPException(404,"Không tìm thấy tài khoản.")
        account=_locked_account(db,account_id)
        prior=db.scalar(select(AdminAudit).where(AdminAudit.actor_id==actor.id,
            AdminAudit.action=="subscription.trial-activated",
            AdminAudit.details["operationId"].as_string()==str(payload.operationId)))
        if prior:
            if prior.details["accountId"]!=str(account_id):
                raise HTTPException(409,"Mã kích hoạt đã dùng cho tài khoản khác.")
            return {"state":"active","endsAt":prior.details["endsAt"],"replayed":True}
        if not account.active or not account.trial_admitted or account.access_tier not in {"agency","province"}:
            raise HTTPException(409,"Tài khoản chưa đủ điều kiện kích hoạt dùng thử.")
        if db.scalar(select(SubscriptionCycle.id).where(SubscriptionCycle.account_id==account.id)):
            raise HTTPException(409,"Tài khoản đã có subscription; không cấp lại tháng dùng thử.")
        now=datetime.now(timezone.utc)
        try:
            enroll(db,account.id,now=now)
            cycle=schedule_plan(db,account.id,tier=account.access_tier,origin="trial",
                operation_key="admin-trial:"+str(payload.operationId),starts_at=now,months=1,now=now)[0]
            grant_due_cycles(db,account.id,now=now)
        except WalletError as error:
            raise HTTPException(409,"Chưa thể kích hoạt. Cần kết thúc các yêu cầu cũ đang chờ và đối soát Credit đang giữ.") from error
        ends_at=utc(cycle.ends_at).isoformat()
        audit(db,actor,"subscription.trial-activated",accountId=str(account.id),
            operationId=str(payload.operationId),startsAt=now.isoformat(),endsAt=ends_at)
        return {"state":"active","endsAt":ends_at,"replayed":False}


def trial_credit_enabled(request):
    if not request.app.state.settings.trial_credit_management:
        raise HTTPException(403, "Quản lý credit thử nghiệm chưa được mở ở môi trường này.")


@router.post("/accounts/{account_id}/trial-credit")
def grant_trial_credit(account_id: uuid.UUID, payload: TrialCreditChange, request: Request):
    trial_credit_enabled(request)
    from .paid_requests import _locked_account, top_up_credits
    with request.app.state.session_factory.begin() as db:
        actor = administrator(request, db, write=True)
        if db.get(UserAccount, account_id) is None:
            raise HTTPException(404, "Không tìm thấy tài khoản.")
        target = _locked_account(db, account_id)
        if db.info.get("real_wallet_enabled") and not wallet_enabled(db,target.id):
            raise HTTPException(409,"Cần kích hoạt ví Credit trước khi cấp Credit theo nguồn.")
        if db.info.get("default_collection_access") and not payload.canCollect:
            raise HTTPException(409,"Tra cứu là quyền mặc định. Hãy khóa tài khoản nếu cần ngừng truy cập.")
        if not target.active or not target.trial_admitted or target.root_department_id is None:
            raise HTTPException(409, "Chỉ cấp quyền/credit cho tài khoản đang hoạt động và đã được mời, gán tỉnh.")
        event = f"trial-grant:{actor.id}:{target.id}:{payload.operationId}"
        details = {"adminId": str(actor.id), "reason": payload.reason, "canCollect": payload.canCollect}
        prior_audit = db.scalar(select(AdminAudit).where(AdminAudit.actor_id == actor.id,
            AdminAudit.action == "trial-credit.updated",
            AdminAudit.details["operationId"].as_string() == str(payload.operationId)))
        if prior_audit is not None:
            prior = prior_audit.details
            if (prior.get("accountId") != str(target.id) or prior.get("amount") != payload.amount
                    or prior.get("canCollect") != payload.canCollect or prior.get("reason") != payload.reason
                    or prior.get("creditSource") != payload.creditSource):
                raise HTTPException(409, "Mã giao dịch đã dùng với nội dung khác.")
            available,reserved=credits(db,target)
            return {"availableCredits": available, "reservedCredits": reserved, "replayed": True}
        existing = db.scalar(select(CreditLedgerEntry).where(CreditLedgerEntry.event_key == event))
        if existing is not None:
            if existing.amount != payload.amount or existing.details != details:
                raise HTTPException(409, "Mã giao dịch đã dùng với nội dung khác.")
            return {"availableCredits": target.credit_balance, "reservedCredits": target.credit_reserved, "replayed": True}
        if not db.info.get("default_collection_access"):
            permission = db.get(AccountCollectionPermission, target.id)
            if permission is None:
                permission = AccountCollectionPermission(account_id=target.id)
                db.add(permission)
            permission.enabled = payload.canCollect
            permission.granted_by = actor.id
        if payload.amount:
            if wallet_enabled(db,target.id):
                if payload.creditSource is None:
                    raise HTTPException(409,"Vui lòng chọn nguồn Credit cần cấp.")
                from .credit_wallet import grant
                now=datetime.now(timezone.utc)
                cycle=active_subscription(db,target.id,now=now)
                if payload.creditSource=="subscription" and cycle is None:
                    raise HTTPException(409,"Cần subscription còn hiệu lực để cấp Credit theo chu kỳ.")
                grant(db,target.id,payload.amount,source=payload.creditSource,operation_key=event,now=now,
                    expires_at=cycle.ends_at if payload.creditSource=="subscription" else None)
            else:
                if payload.creditSource is not None:
                    raise HTTPException(409,"Tài khoản chưa bật Credit theo nguồn.")
                top_up_credits(db, target.id, payload.amount, event_key=event, details=details)
        audit(db, actor, "trial-credit.updated", accountId=str(target.id), operationId=str(payload.operationId),
              amount=payload.amount, canCollect=payload.canCollect, reason=payload.reason,
              **({"creditSource":payload.creditSource} if payload.creditSource is not None else {}))
        available,reserved=credits(db,target)
        return {"availableCredits": available, "reservedCredits": reserved, "replayed": False}


@router.get("/accounts/{account_id}/credits")
def credit_ledger(account_id: uuid.UUID, request: Request):
    trial_credit_enabled(request)
    with request.app.state.session_factory() as db:
        administrator(request, db)
        account = db.get(UserAccount, account_id)
        if account is None:
            raise HTTPException(404, "Không tìm thấy tài khoản.")
        if wallet_enabled(db,account.id):
            from .models import CreditWalletEvent
            available,reserved=credits(db,account)
            return {"availableCredits":available,"reservedCredits":reserved,"walletMode":"sources",
                "items":[{"type":"redemption" if r.details.get("reason")=="subscription_redemption" else r.kind,
                    "amount":r.amount,"availableAfter":r.details.get("availableAfter",0),
                    "reservedAfter":r.details.get("reservedAfter",0),"at":r.created_at.isoformat(),"details":r.details}
                    for r in db.scalars(select(CreditWalletEvent).where(CreditWalletEvent.account_id==account.id)
                        .order_by(CreditWalletEvent.created_at.desc(),CreditWalletEvent.id.desc()).limit(100))]}
        return {"availableCredits": account.credit_balance, "reservedCredits": account.credit_reserved,
                "items": [{"type": row.entry_type, "amount": row.amount, "availableAfter": row.available_after,
                           "reservedAfter": row.reserved_after, "at": row.created_at.isoformat(), "details": row.details}
                          for row in db.scalars(select(CreditLedgerEntry).where(CreditLedgerEntry.account_id == account_id)
                            .order_by(CreditLedgerEntry.created_at.desc(), CreditLedgerEntry.id.desc()).limit(100))]}
