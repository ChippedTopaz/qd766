"""Explicit opt-in adapter; never auto-classify or migrate legacy balances."""
from datetime import datetime, timezone
from sqlalchemy import select
from .models import CreditWalletEnrollment, PaidDataRequest, SubscriptionCycle
from .credit_wallet import balance, utc, WalletError
from .paid_requests import _locked_account


def enabled(db, account_id):
    return bool(db.info.get("source_wallet_enabled") and db.get(CreditWalletEnrollment, account_id))


def enroll(db, account_id, *, now):
    if not db.info.get("source_wallet_enabled"):
        raise WalletError("Source wallet is disabled")
    account=_locked_account(db, account_id)
    if db.get(CreditWalletEnrollment, account_id):
        return
    if account.credit_reserved:
        raise WalletError("Reconcile legacy reserved Credit before enrolling")
    if db.scalar(select(PaidDataRequest.id).where(PaidDataRequest.account_id == account_id,
            PaidDataRequest.state.in_(("reserved", "waiting")))):
        raise WalletError("Finish pending legacy requests before enrolling")
    db.add(CreditWalletEnrollment(account_id=account_id, created_at=utc(now)))
    db.flush()


def credits(db, account, *, now=None):
    now = now or datetime.now(timezone.utc)
    if enabled(db, account.id):
        values = balance(db, account.id, now=now)
        return values["available"], values["reserved"]
    return account.credit_balance, account.credit_reserved


def active_subscription(db, account_id, *, now):
    return db.scalar(select(SubscriptionCycle).where(SubscriptionCycle.account_id == account_id,
        SubscriptionCycle.starts_at <= now, SubscriptionCycle.ends_at > now))


def subscription_summary(db, account, *, now=None):
    """Read-only admin projection: never grant Credit or activate a trial on GET."""
    if not enabled(db, account.id):
        return None
    now=utc(now or datetime.now(timezone.utc))
    current=active_subscription(db,account.id,now=now)
    future=db.scalar(select(SubscriptionCycle).where(SubscriptionCycle.account_id==account.id,
        SubscriptionCycle.starts_at>now).order_by(SubscriptionCycle.starts_at).limit(1))
    previous=db.scalar(select(SubscriptionCycle).where(SubscriptionCycle.account_id==account.id,
        SubscriptionCycle.ends_at<=now).order_by(SubscriptionCycle.ends_at.desc()).limit(1))
    cycle=current or future or previous
    values=balance(db,account.id,now=now)
    return {"state":"active" if current else "scheduled" if future else "expired" if previous else "none",
        "origin":cycle.origin if cycle else None,
        "endsAt":utc(cycle.ends_at).isoformat() if cycle else None,
        "startsAt":utc(cycle.starts_at).isoformat() if cycle else None,
        "nextStartsAt":utc(future.starts_at).isoformat() if future else None,
        "subscriptionCredits":values["subscription"],"purchasedCredits":values["purchased"]}
