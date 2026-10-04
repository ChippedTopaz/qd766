"""Review old accounts and activate only explicitly selected eligible invitees.

Caller owns transaction. Never classifies legacy Credit or unlocks accounts.
"""
import uuid
from sqlalchemy import select, func
from .models import UserAccount, TrialInvitation, SubscriptionCycle, CreditLot, CreditWalletEvent, CreditLedgerEntry, PaidDataRequest, AdminAudit
from .paid_requests import _locked_account
from .credit_wallet import WalletError, utc
from .invited_trial import activate_invited_trial


def review(db, account):
    invitation=None
    reason="eligible"
    if account.role=="admin":reason="admin_excluded"
    elif not account.active:reason="locked"
    elif not account.trial_admitted or not account.root_department_id:reason="not_admitted_or_unassigned"
    elif not account.external_subject.startswith("google:"):reason="not_google_account"
    elif account.credit_reserved or db.scalar(select(PaidDataRequest.id).where(
            PaidDataRequest.account_id==account.id,PaidDataRequest.state.in_(("reserved","waiting")))):
        reason="pending_legacy_credit"
    elif account.credit_balance:reason="legacy_balance_review_required"
    elif db.scalar(select(SubscriptionCycle.id).where(SubscriptionCycle.account_id==account.id)):
        reason="subscription_already_exists"
    elif db.scalar(select(CreditLot.id).where(CreditLot.account_id==account.id)) or db.scalar(
            select(CreditWalletEvent.id).where(CreditWalletEvent.account_id==account.id)):
        reason="wallet_history_review_required"
    else:
        deltas=db.execute(select(func.coalesce(func.sum(CreditLedgerEntry.available_delta),0),
            func.coalesce(func.sum(CreditLedgerEntry.reserved_delta),0)).where(
            CreditLedgerEntry.account_id==account.id)).one()
        if tuple(deltas)!=(account.credit_balance,account.credit_reserved):reason="legacy_ledger_mismatch"
        else:
            invitation=db.scalar(select(TrialInvitation).where(TrialInvitation.used_by==account.id,
                TrialInvitation.used_at.is_not(None),TrialInvitation.revoked_at.is_(None),
                TrialInvitation.root_department_id==account.root_department_id,
                TrialInvitation.access_tier==account.access_tier,
                TrialInvitation.unit_department_id==account.unit_department_id).order_by(
                TrialInvitation.used_at.desc(),TrialInvitation.id).limit(1))
            if invitation is None:reason="redeemed_matching_invitation_required"
    return {"accountId":str(account.id),"accessTier":account.access_tier,
            "eligible":reason=="eligible","reason":reason},invitation


def apply_selected(db, *, account_ids, administrator_id, operation_id, now):
    if not db.info.get("real_wallet_enabled") or not db.info.get("source_wallet_enabled"):
        raise WalletError("Explicit real wallet transition is required")
    actor=_locked_account(db,administrator_id)
    if (not actor.active or not actor.trial_admitted or actor.role!="admin"
            or (actor.email or "").lower()!="vietnt89@gmail.com" or not actor.external_subject.startswith("google:")):
        raise WalletError("Verified owner administrator required")
    selected=sorted(set(uuid.UUID(str(value)) for value in account_ids),key=str)
    if not selected or len(selected)!=len(account_ids):raise WalletError("Select distinct reviewed accounts")
    operation=uuid.UUID(str(operation_id))
    prior=db.scalar(select(AdminAudit).where(AdminAudit.actor_id==actor.id,
        AdminAudit.action=="subscription.backfill-approved",
        AdminAudit.details["operationId"].as_string()==str(operation)))
    if prior:
        if prior.details["accountIds"]!=[str(value) for value in selected]:
            raise WalletError("Backfill operation replay differs")
        return {"activated":0,"replayed":True}
    # Serialize each account before re-review; no bulk eligibility assumptions.
    items=[]
    for identity in selected:
        account=_locked_account(db,identity)
        report,invitation=review(db,account)
        if not report["eligible"]:raise WalletError("Selected account is no longer eligible: "+report["reason"])
        invitation=db.scalar(select(TrialInvitation).where(TrialInvitation.id==invitation.id)
            .with_for_update().execution_options(populate_existing=True))
        if invitation.revoked_at or invitation.used_by!=account.id or invitation.used_at is None:
            raise WalletError("Invitation eligibility changed during transition")
        items.append((account,invitation))
    for account,invitation in items:
        if not activate_invited_trial(db,account.id,invitation,now=now,backfill=True):
            raise WalletError("Trial activation changed during transition")
    db.add(AdminAudit(actor_id=actor.id,action="subscription.backfill-approved",details={
        "operationId":str(operation),"accountIds":[str(value) for value in selected],
        "startsAt":utc(now).isoformat(),"creditPerTrial":100}))
    db.flush()
    return {"activated":len(selected),"replayed":False}
