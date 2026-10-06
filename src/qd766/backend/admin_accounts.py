"""Read-only, bounded-query account list; no wallet grants or expiry writes."""
from datetime import datetime, timezone
from sqlalchemy import select
from .models import AccountCollectionPermission, CreditWalletEnrollment, CreditLot, SubscriptionCycle
from .credit_wallet import utc


def account_projections(db, users, *, now=None):
    now = utc(now or datetime.now(timezone.utc))
    ids = [a.id for a in users]
    if not ids:
        return {}
    source_enabled = bool(db.info.get("source_wallet_enabled"))
    enrolled = set(db.scalars(select(CreditWalletEnrollment.account_id).where(
        CreditWalletEnrollment.account_id.in_(ids)))) if source_enabled else set()
    balances = {key: {"subscription": 0, "purchased": 0, "reserved": 0} for key in enrolled}
    if enrolled:
        for lot in db.scalars(select(CreditLot).where(CreditLot.account_id.in_(enrolled))):
            values = balances[lot.account_id]
            values["reserved"] += lot.reserved
            if lot.expires_at is None or utc(lot.expires_at) > now:
                values[lot.source] += lot.available
    cycles = {}
    if source_enabled:
        for cycle in db.scalars(select(SubscriptionCycle).where(SubscriptionCycle.account_id.in_(ids))):
            cycles.setdefault(cycle.account_id, []).append(cycle)
    default_access = bool(db.info.get("default_collection_access"))
    permissions = {} if default_access else dict(db.execute(select(
        AccountCollectionPermission.account_id, AccountCollectionPermission.enabled).where(
        AccountCollectionPermission.account_id.in_(ids))).all())
    result = {}
    for account in users:
        summary = None
        available, reserved = account.credit_balance, account.credit_reserved
        if account.id in enrolled:
            values = balances[account.id]
            available = values["subscription"] + values["purchased"]
            reserved = values["reserved"]
            history = cycles.get(account.id, [])
            current = next((c for c in history if utc(c.starts_at) <= now < utc(c.ends_at)), None)
            future = min((c for c in history if utc(c.starts_at) > now), key=lambda c: utc(c.starts_at), default=None)
            previous = max((c for c in history if utc(c.ends_at) <= now), key=lambda c: utc(c.ends_at), default=None)
            cycle = current or future or previous
            summary = {"state": "active" if current else "scheduled" if future else "expired" if previous else "none",
                       "origin": cycle.origin if cycle else None,
                       "endsAt": utc(cycle.ends_at).isoformat() if cycle else None,
                       "startsAt": utc(cycle.starts_at).isoformat() if cycle else None,
                       "nextStartsAt": utc(future.starts_at).isoformat() if future else None,
                       "subscriptionCredits": values["subscription"], "purchasedCredits": values["purchased"]}
        result[account.id] = {"credits": available, "reservedCredits": reserved,
            "walletMode": "sources" if account.id in enrolled else "legacy", "subscription": summary,
            "canCollect": bool(account.active and account.trial_admitted and account.root_department_id)
                if default_access else permissions.get(account.id) is True,
            "canActivateTrial": bool(source_enabled and account.active and account.trial_admitted
                and account.access_tier in {"agency", "province"} and not cycles.get(account.id))}
    return result
