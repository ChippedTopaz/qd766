"""One free calendar month + 100 Credit on valid invitation redemption.

Called only by explicit source-wallet modes. Caller owns transaction.
"""
from sqlalchemy import select
from .models import AdminAudit, SubscriptionCycle
from .paid_requests import _locked_account
from .subscriptions import schedule_plan, grant_due_cycles
from .wallet_access import enroll
from .credit_wallet import WalletError, utc


def activate_invited_trial(db, account_id, invitation, *, now, backfill=False):
    if not db.info.get("source_wallet_enabled"):
        raise WalletError("Source wallet trial is disabled")
    account=_locked_account(db,account_id)
    if not account.active or not account.trial_admitted or invitation.used_by!=account.id:
        raise WalletError("Valid redeemed invitation required")
    # Returning/login again/reinviting never extends or grants a second trial.
    if db.scalar(select(SubscriptionCycle.id).where(SubscriptionCycle.account_id==account.id)):
        return False
    enroll(db,account.id,now=now)
    cycle=schedule_plan(db,account.id,tier="agency" if account.access_tier=="agency" else "province",
        origin="trial",operation_key="invitation-trial:"+str(invitation.id),
        starts_at=now,months=1,now=now)[0]
    grant_due_cycles(db,account.id,now=now)
    db.add(AdminAudit(actor_id=invitation.created_by,action="subscription.invited-trial-started",
        details={"accountId":str(account.id),"invitationId":str(invitation.id),
                 "startsAt":utc(now).isoformat(),"endsAt":utc(cycle.ends_at).isoformat(),
                 "credit":100,"backfill":backfill}))
    db.flush()
    return True
