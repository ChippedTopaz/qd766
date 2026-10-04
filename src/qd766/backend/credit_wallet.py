"""Source-aware Credit accounting core. Not wired to production requests/payments yet.

Caller owns one transaction. Every mutation locks the account, records an event,
and flushes; never commit here. Existing legacy balances are deliberately untouched.
"""
import uuid
from datetime import datetime, timedelta, timezone
from sqlalchemy import select
from .models import CreditLot, CreditHold, CreditWalletEvent
from .paid_requests import _locked_account


class WalletError(ValueError):
    pass


def utc(value):
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)  # SQLite returns naive UTC.
    return value.astimezone(timezone.utc)


def valid_amount(amount):
    if type(amount) is not int or not 0 < amount <= 10_000_000:
        raise WalletError("Credit amount must be a positive integer")


def event(db, account_id, key, kind, amount, details, now):
    db.flush()
    values=balance(db,account_id,now=now)
    details={**details,"availableAfter":values["available"],"reservedAfter":values["reserved"]}
    db.add(CreditWalletEvent(account_id=account_id,event_key=key,kind=kind,
                            amount=amount,details=details,created_at=now))
    db.flush()


def grant(db, account_id, amount, *, source, operation_key, now, expires_at=None):
    valid_amount(amount)
    if not operation_key or len(operation_key)>220:
        raise WalletError("Invalid operation key")
    now=utc(now)
    if source not in {"subscription","purchased"}:
        raise WalletError("Unknown Credit source")
    expires_at=utc(expires_at) if expires_at else None
    if (source=="purchased" and expires_at is not None) or (source=="subscription" and
            (expires_at is None or expires_at<=now)):
        raise WalletError("Invalid expiry for Credit source")
    _locked_account(db,account_id)
    key="grant:"+operation_key
    previous=db.scalar(select(CreditWalletEvent).where(
        CreditWalletEvent.account_id==account_id,CreditWalletEvent.event_key==key))
    if previous:
        if previous.amount!=amount or previous.details["source"]!=source or previous.details["expiresAt"]!=(expires_at.isoformat() if expires_at else None):
            raise WalletError("Operation replay differs from original grant")
        return db.get(CreditLot,uuid.UUID(previous.details["lotId"]))
    lot=CreditLot(account_id=account_id,source=source,available=amount,reserved=0,
                  expires_at=expires_at,created_at=now)
    db.add(lot);db.flush()
    event(db,account_id,key,"grant",amount,{"source":source,"lotId":str(lot.id),
          "expiresAt":expires_at.isoformat() if expires_at else None},now)
    return lot


def expire(db, account_id, *, now):
    now=utc(now);_locked_account(db,account_id)
    lots=db.scalars(select(CreditLot).where(CreditLot.account_id==account_id,
        CreditLot.source=="subscription",CreditLot.expires_at<=now,CreditLot.available>0)).all()
    for lot in lots:
        amount=lot.available;lot.available=0
        # Held Credit survives expiry until the request completes or is refunded.
        event(db,account_id,"expire:"+str(lot.id),"expire",amount,{"source":lot.source,"lotId":str(lot.id)},now)
    db.flush()


def balance(db, account_id, *, now):
    # Read-only projection; no automatic expiry mutation on a GET.
    now=utc(now)
    values={"subscription":0,"purchased":0,"reserved":0}
    for lot in db.scalars(select(CreditLot).where(CreditLot.account_id==account_id)):
        values["reserved"]+=lot.reserved
        if lot.expires_at is None or utc(lot.expires_at)>now:
            values[lot.source]+=lot.available
    return {**values,"available":values["subscription"]+values["purchased"]}


def reserve(db, account_id, amount, *, request_key, now):
    valid_amount(amount)
    if not request_key or len(request_key)>220:
        raise WalletError("Invalid request key")
    now=utc(now);_locked_account(db,account_id)
    old=db.scalar(select(CreditHold).where(CreditHold.account_id==account_id,CreditHold.request_key==request_key))
    if old:
        if old.amount!=amount:
            raise WalletError("Request replay differs from original hold")
        return old
    # Verify sufficiency before changing any balances or writing expiration events.
    if balance(db,account_id,now=now)["available"]<amount:
        raise WalletError("Insufficient Credit")
    expire(db,account_id,now=now)
    lots=db.scalars(select(CreditLot).where(CreditLot.account_id==account_id,CreditLot.available>0)).all()
    # Proposed tie-break within subscription: soonest expiry first; deterministic.
    lots.sort(key=lambda lot:(0 if lot.source=="subscription" else 1,
        utc(lot.expires_at) if lot.expires_at else datetime.max.replace(tzinfo=timezone.utc),
        utc(lot.created_at),str(lot.id)))
    remaining=amount;allocations=[]
    for lot in lots:
        if not remaining:break
        take=min(remaining,lot.available)
        lot.available-=take;lot.reserved+=take;remaining-=take
        allocations.append({"lotId":str(lot.id),"source":lot.source,"amount":take})
    hold=CreditHold(account_id=account_id,request_key=request_key,state="reserved",
                    amount=amount,allocations=allocations,created_at=now)
    db.add(hold);db.flush()
    event(db,account_id,"reserve:"+request_key,"reserve",amount,{"allocations":allocations},now)
    return hold


def finish(db, account_id, *, request_key, outcome, now):
    if outcome not in {"charge","refund"}:
        raise WalletError("Unknown settlement outcome")
    now=utc(now);_locked_account(db,account_id)
    hold=db.scalar(select(CreditHold).where(CreditHold.account_id==account_id,CreditHold.request_key==request_key))
    if hold is None:raise WalletError("Unknown hold")
    target="charged" if outcome=="charge" else "refunded"
    if hold.state==target:return hold  # Idempotent acknowledgement.
    if hold.state!="reserved":raise WalletError("Hold already finalized with another outcome")
    restored=[]
    for item in hold.allocations:
        lot=db.get(CreditLot,uuid.UUID(item["lotId"]))
        if lot is None or lot.account_id!=account_id or lot.reserved<item["amount"]:
            raise WalletError("Invalid Credit allocation")
        lot.reserved-=item["amount"]
        if outcome=="refund":
            destination=lot
            if lot.source=="subscription" and utc(lot.expires_at)<=now:
                destination=CreditLot(account_id=account_id,source="subscription",available=0,reserved=0,
                    expires_at=now+timedelta(days=7),created_at=now)
                db.add(destination);db.flush()
            destination.available+=item["amount"]
            restored.append({"originalLotId":str(lot.id),"lotId":str(destination.id),
                "source":destination.source,"amount":item["amount"],
                "expiresAt":utc(destination.expires_at).isoformat() if destination.expires_at else None})
    hold.state=target
    event(db,account_id,outcome+":"+request_key,outcome,hold.amount,
          {"allocations":hold.allocations,"restored":restored},now)
    db.flush()
    return hold
