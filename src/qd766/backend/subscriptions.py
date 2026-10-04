"""Subscription cycle core, not exposed through a public API yet.

Caller owns the transaction; account locks serialize every mutation.
"""
import calendar
from datetime import timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select

from .credit_wallet import WalletError, balance, event, expire, grant, utc
from .models import CreditLot, SubscriptionCycle
from .paid_requests import _locked_account


def monthly_boundary(anchor, offset):
    """Calendar months in Vietnam, always derived from the original anchor."""
    if type(offset) is not int or offset < 0:
        raise WalletError("Invalid month offset")
    local = utc(anchor).astimezone(ZoneInfo("Asia/Ho_Chi_Minh"))
    ordinal = local.year * 12 + local.month - 1 + offset
    year, month_zero = divmod(ordinal, 12)
    month = month_zero + 1
    day = min(local.day, calendar.monthrange(year, month)[1])
    return utc(local.replace(year=year, month=month, day=day))


def _key(value):
    if not isinstance(value, str) or not value.strip() or len(value) > 180:
        raise WalletError("Invalid subscription operation key")


def _dates(start, end):
    start, end = utc(start), utc(end)
    if not timedelta(days=28) <= end - start <= timedelta(days=31):
        raise WalletError("Expected one monthly cycle with explicit boundaries")
    return start, end


def _overlap(db, account_id, start, end):
    return db.scalar(select(SubscriptionCycle).where(
        SubscriptionCycle.account_id == account_id,
        SubscriptionCycle.starts_at < end,
        SubscriptionCycle.ends_at > start))


def schedule_cycle(db, account_id, *, tier, origin, operation_key,
                   starts_at, ends_at, now):
    """Schedule one approved trial/paid month, never grant future Credit early.

    Payment verification and the trial start are caller responsibilities; this
    function is deliberately not a checkout or user-selectable plan endpoint.
    """
    _key(operation_key)
    if tier not in {"agency", "province"} or origin not in {"trial", "paid"}:
        raise WalletError("Unsupported subscription tier or origin")
    start, end = _dates(starts_at, ends_at)
    _locked_account(db, account_id)
    old = db.scalar(select(SubscriptionCycle).where(
        SubscriptionCycle.account_id == account_id,
        SubscriptionCycle.operation_key == operation_key))
    if old:
        if (old.tier, old.origin, utc(old.starts_at), utc(old.ends_at)) != (tier, origin, start, end):
            raise WalletError("Subscription replay differs from original cycle")
        return old
    if _overlap(db, account_id, start, end):
        raise WalletError("Subscription cycles must not overlap")
    if origin == "trial" and db.scalar(select(SubscriptionCycle).where(
            SubscriptionCycle.account_id == account_id,
            SubscriptionCycle.origin == "trial")):
        raise WalletError("Trial already granted")
    cycle = SubscriptionCycle(account_id=account_id, operation_key=operation_key,
        tier=tier, origin=origin, starts_at=start, ends_at=end,
        included_credit=100 if origin == "trial" or tier == "agency" else 200,
        created_at=utc(now))
    db.add(cycle)
    db.flush()
    return cycle


def grant_due_cycles(db, account_id, *, now):
    """Catch up only the currently active month; never revive missed expired months."""
    now = utc(now)
    _locked_account(db, account_id)
    expire(db, account_id, now=now)
    cycles = db.scalars(select(SubscriptionCycle).where(
        SubscriptionCycle.account_id == account_id,
        SubscriptionCycle.starts_at <= now, SubscriptionCycle.ends_at > now,
        SubscriptionCycle.granted_at.is_(None),
        SubscriptionCycle.included_credit > 0)).all()
    for cycle in cycles:
        grant(db, account_id, cycle.included_credit, source="subscription",
              operation_key="cycle:" + str(cycle.id), now=now, expires_at=cycle.ends_at)
        cycle.granted_at = now
    db.flush()
    return len(cycles)


def schedule_plan(db, account_id, *, tier, origin, operation_key, starts_at, months, now):
    """Record approved access; grant only when each month becomes active."""
    _key(operation_key)
    if len(operation_key) > 160:
        raise WalletError("Plan operation key is too long")
    if months not in {1, 6, 12} or type(months) is not int or (origin == "trial" and months != 1):
        raise WalletError("Unsupported subscription duration")
    _locked_account(db, account_id)
    existing = db.scalars(select(SubscriptionCycle).where(
        SubscriptionCycle.account_id == account_id,
        SubscriptionCycle.operation_key.startswith(f"plan:{operation_key}:", autoescape=True))).all()
    if existing and len(existing) != months:
        raise WalletError("Plan replay differs from original duration")
    return [schedule_cycle(db, account_id, tier=tier, origin=origin,
            operation_key=f"plan:{operation_key}:{index}",
            starts_at=monthly_boundary(starts_at, index),
            ends_at=monthly_boundary(starts_at, index + 1), now=now)
            for index in range(months)]


def redeem_month(db, account_id, *, operation_key, now, expected_cost=None):
    """Atomically debit only purchased Credit and record one calendar access month.

    This does not update legacy account access/balances or add included Credit.
    """
    _key(operation_key)
    now = utc(now)
    account = _locked_account(db, account_id)
    old = db.scalar(select(SubscriptionCycle).where(
        SubscriptionCycle.account_id == account_id,
        SubscriptionCycle.operation_key == operation_key))
    if old:
        if old.origin != "redemption":
            raise WalletError("Operation key already used for another cycle")
        if expected_cost is not None and expected_cost != (300 if old.tier=="agency" else 600):
            raise WalletError("Confirmed redemption cost differs from original operation")
        return old
    tier = account.access_tier
    if tier not in {"agency", "province"}:
        raise WalletError("National scope is not redeemable")
    start, end = _dates(now, monthly_boundary(now, 1))
    # Renewal by Credit is available only after all approved access has expired.
    if db.scalar(select(SubscriptionCycle).where(
            SubscriptionCycle.account_id == account_id, SubscriptionCycle.ends_at > now)):
        raise WalletError("Subscription has not expired")
    cost = 300 if tier == "agency" else 600
    if expected_cost is not None and expected_cost != cost:
        raise WalletError("Redemption cost changed; confirm again")
    if balance(db, account_id, now=now)["purchased"] < cost:
        raise WalletError("Insufficient purchased Credit")
    lots = db.scalars(select(CreditLot).where(CreditLot.account_id == account_id,
        CreditLot.source == "purchased", CreditLot.available > 0)
        .order_by(CreditLot.created_at, CreditLot.id)).all()
    remaining, allocations = cost, []
    for lot in lots:
        take = min(remaining, lot.available)
        lot.available -= take
        allocations.append({"lotId":str(lot.id), "source":"purchased", "amount":take})
        remaining -= take
        if not remaining:
            break
    cycle = SubscriptionCycle(account_id=account_id, operation_key=operation_key,
        tier=tier, origin="redemption", starts_at=start, ends_at=end,
        included_credit=0, created_at=now)
    db.add(cycle)
    db.flush()
    event(db, account_id, "redeem:" + operation_key, "charge", cost,
          {"reason":"subscription_redemption", "cycleId":str(cycle.id),
           "tier":tier, "endsAt":end.isoformat(), "allocations":allocations}, now)
    return cycle
