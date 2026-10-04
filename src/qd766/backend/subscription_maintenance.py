"""Explicit opt-in cycle maintenance; no enrollment, checkout or trial activation.

Each account commits independently. Existing account locks and event keys make
overlapping runs safe; failed accounts remain eligible for the next run.
"""
from sqlalchemy import func, select

from .credit_wallet import WalletError, utc
from .models import CreditWalletEnrollment, CreditWalletEvent
from .paid_requests import _locked_account
from .subscriptions import grant_due_cycles


def _expired_total(db, account_id):
    return db.scalar(select(func.coalesce(func.sum(CreditWalletEvent.amount), 0)).where(
        CreditWalletEvent.account_id == account_id, CreditWalletEvent.kind == "expire"))


def run_subscription_maintenance(factory, *, now, batch_size=100):
    """Expire unused subscription Credit and grant approved current cycles only.

    No changes to legacy Credit, purchased Credit, holds, account access or jobs.
    The caller must opt in the session factory; production has no scheduler yet.
    """
    if type(batch_size) is not int or not 1 <= batch_size <= 1000:
        raise WalletError("Invalid maintenance batch size")
    now = utc(now)
    with factory() as db:
        if not db.info.get("source_wallet_enabled"):
            raise WalletError("Source wallet maintenance is disabled")
    result = {"scanned": 0, "processed": 0, "grantedCycles": 0,
              "expiredCredit": 0, "failures": []}
    cursor = None
    while True:
        with factory() as db:
            query = select(CreditWalletEnrollment.account_id).order_by(
                CreditWalletEnrollment.account_id).limit(batch_size)
            if cursor is not None:
                query = query.where(CreditWalletEnrollment.account_id > cursor)
            accounts = list(db.scalars(query))
        if not accounts:
            return result
        for account_id in accounts:
            result["scanned"] += 1
            try:
                with factory.begin() as db:
                    _locked_account(db, account_id)
                    before = _expired_total(db, account_id)
                    granted = grant_due_cycles(db, account_id, now=now)
                    expired = _expired_total(db, account_id) - before
                # Count only committed changes, not an attempted transaction.
                result["processed"] += 1
                result["grantedCycles"] += granted
                result["expiredCredit"] += expired
            except Exception as error:
                # Never expose connection strings, tokens or database errors.
                result["failures"].append({"accountId": str(account_id),
                                           "type": type(error).__name__})
        cursor = accounts[-1]
