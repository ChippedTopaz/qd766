"""Exercise wallet core on restored PostgreSQL, rolling back every test write."""
import argparse
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from sqlalchemy import create_engine, func, select, text
from sqlalchemy.orm import Session

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from rehearse_credit_restore import restore_url, fingerprint
from qd766.backend.public_deployment import read_config
from qd766.backend.database import create_session_factory
from qd766.backend.wallet_runtime import verify_real_wallet_schema
from qd766.backend.models import Department, UserAccount, CreditWalletEvent, CreditHold
from qd766.backend.credit_wallet import balance, grant, reserve, finish, expire, WalletError
from qd766.backend.subscriptions import schedule_plan, grant_due_cycles, redeem_month, monthly_boundary
from qd766.backend.wallet_access import enroll


def require(value, message):
    if not value:
        raise AssertionError(message)


def scenarios(db):
    """Only new UUID test accounts; caller must rollback and never commit."""
    checks = []
    now = datetime(2026, 10, 4, tzinfo=timezone.utc)
    department = Department(id=uuid.uuid4(), name="Restore wallet rehearsal ONLY", attributes={})
    db.add(department)
    db.flush()

    def account(tier="agency"):
        value = UserAccount(id=uuid.uuid4(), external_subject="restore-wallet:" + uuid.uuid4().hex,
            display_name="Rollback-only test", access_tier=tier, root_department_id=department.id,
            unit_department_id=department.id if tier == "agency" else None,
            trial_admitted=True, active=True, credit_balance=111, credit_reserved=0)
        db.add(value)
        db.flush()
        enroll(db, value.id, now=now)
        return value

    def events(value, kind=None):
        query = select(func.count()).select_from(CreditWalletEvent).where(CreditWalletEvent.account_id == value.id)
        if kind:
            query = query.where(CreditWalletEvent.kind == kind)
        return db.scalar(query)

    trial = account()
    plan = schedule_plan(db, trial.id, tier="agency", origin="trial", operation_key="trial",
                         starts_at=now, months=1, now=now)
    require(grant_due_cycles(db, trial.id, now=now) == 1, "Trial grant missing")
    require(grant_due_cycles(db, trial.id, now=now) == 0, "Trial grant repeated")
    require(balance(db, trial.id, now=now)["available"] == 100, "Trial should grant 100")
    held = reserve(db, trial.id, 5, request_key="charge", now=now)
    require(reserve(db, trial.id, 5, request_key="charge", now=now).id == held.id, "Duplicate hold")
    require(balance(db, trial.id, now=now)["reserved"] == 5, "Hold missing")
    finish(db, trial.id, request_key="charge", outcome="charge", now=now)
    finish(db, trial.id, request_key="charge", outcome="charge", now=now)
    require(balance(db, trial.id, now=now)["available"] == 95, "Charge differs from 5")
    require(events(trial, "charge") == 1, "Repeated charge event")
    checks.append("trial_100_hold_5_charge_once")

    reserve(db, trial.id, 5, request_key="refund", now=now)
    finish(db, trial.id, request_key="refund", outcome="refund", now=now)
    finish(db, trial.id, request_key="refund", outcome="refund", now=now)
    require(balance(db, trial.id, now=now)["available"] == 95, "Refund differs from hold")
    require(events(trial, "refund") == 1, "Repeated refund event")
    before = events(trial)
    try:
        reserve(db, trial.id, 96, request_key="insufficient", now=now)
    except WalletError:
        pass
    else:
        raise AssertionError("Insufficient Credit accepted")
    require(events(trial) == before, "Insufficient request wrote ledger")
    require(db.scalar(select(func.count()).select_from(CreditHold).where(
        CreditHold.account_id == trial.id, CreditHold.request_key == "insufficient")) == 0, "Stranded hold")
    expire(db, trial.id, now=plan[0].ends_at)
    expire(db, trial.id, now=plan[0].ends_at)
    require(balance(db, trial.id, now=plan[0].ends_at)["available"] == 0, "Trial Credit did not expire")
    require(events(trial, "expire") == 1, "Repeated expiry event")
    checks.append("refund_once_insufficient_no_write_unused_subscription_expires")

    mixed = account()
    grant(db, mixed.id, 3, source="subscription", operation_key="short-cycle", now=now,
          expires_at=now + timedelta(days=1))
    grant(db, mixed.id, 10, source="purchased", operation_key="purchase", now=now)
    hold = reserve(db, mixed.id, 5, request_key="mixed", now=now)
    require([(a["source"], a["amount"]) for a in hold.allocations] ==
            [("subscription", 3), ("purchased", 2)], "Source priority differs")
    later = now + timedelta(days=2)
    expire(db, mixed.id, now=later)
    require(balance(db, mixed.id, now=later)["reserved"] == 5, "Expiry destroyed held Credit")
    finish(db, mixed.id, request_key="mixed", outcome="refund", now=later)
    require(balance(db, mixed.id, now=later) == dict(subscription=3, purchased=10, reserved=0, available=13),
            "Refund sources differ")
    expire(db, mixed.id, now=later + timedelta(days=7))
    require(balance(db, mixed.id, now=later + timedelta(days=7))["available"] == 10,
            "Seven-day grace or purchased carryover differs")
    checks.append("subscription_first_refund_same_sources_7_day_grace_purchase_carries")

    for tier, cost in (("agency", 300), ("province", 600)):
        value = account(tier)
        grant(db, value.id, cost, source="purchased", operation_key="purchase", now=now)
        cycle = redeem_month(db, value.id, operation_key="renew", now=now, expected_cost=cost)
        require(redeem_month(db, value.id, operation_key="renew", now=now, expected_cost=cost).id == cycle.id,
                "Redemption repeated")
        require(balance(db, value.id, now=now)["available"] == 0, "Redemption amount differs")
        require(cycle.included_credit == 0 and grant_due_cycles(db, value.id, now=now) == 0,
                "Redeemed month included Credit")
        require(events(value, "charge") == 1, "Redemption charged twice")
        checks.append(f"{tier}_redemption_{cost}_once_no_included_credit")

    for tier, amount in (("agency", 100), ("province", 200)):
        value = account(tier)
        anchor = datetime(2027, 1, 31, 23, 30, tzinfo=ZoneInfo("Asia/Ho_Chi_Minh"))
        schedule_plan(db, value.id, tier=tier, origin="paid", operation_key="six-months",
                      starts_at=anchor, months=6, now=anchor)
        require(grant_due_cycles(db, value.id, now=anchor) == 1, "First cycle not granted")
        require(balance(db, value.id, now=anchor)["subscription"] == amount, "Future cycles granted early")
        boundary = monthly_boundary(anchor, 1)
        require(grant_due_cycles(db, value.id, now=boundary) == 1, "Second cycle not granted")
        require(grant_due_cycles(db, value.id, now=boundary) == 0, "Second cycle granted twice")
        require(balance(db, value.id, now=boundary)["subscription"] == amount, "Old cycle carried over")
        dates = [monthly_boundary(anchor, i).astimezone(ZoneInfo("Asia/Ho_Chi_Minh")) for i in (1, 2)]
        require([(v.month, v.day, v.hour) for v in dates] == [(2, 28, 23), (3, 31, 23)], "Calendar anchor drift")
        checks.append(f"{tier}_monthly_{amount}_not_upfront_calendar_anchor")

    # Test-only sentinel legacy balance proves the wallet did not rewrite it.
    db.flush()
    accounts = db.scalars(select(UserAccount).where(UserAccount.external_subject.like("restore-wallet:%"))).all()
    require(all(a.credit_balance == 111 and a.credit_reserved == 0 for a in accounts), "Legacy balance changed")
    checks.append("legacy_balance_untouched")
    return checks


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", required=True)
    parser.add_argument("--connection-file", type=Path, required=True)
    args = parser.parse_args()
    engine = None
    try:
        url = restore_url(read_config(args.connection_file), args.database)
        engine = create_engine(url, connect_args={"connect_timeout": 5, "options": "-c search_path=public"})
        verify_real_wallet_schema(create_session_factory(engine))
        before = fingerprint(engine)
        with engine.connect() as connection:
            transaction = connection.begin()
            try:
                connection.execute(text("SET LOCAL lock_timeout = '5s'"))
                connection.execute(text("SET LOCAL statement_timeout = '15s'"))
                with Session(bind=connection, expire_on_commit=False, info={"source_wallet_enabled": True,
                        "real_wallet_enabled": True, "default_collection_access": True}) as db:
                    checks = scenarios(db)
            finally:
                if transaction.is_active:
                    transaction.rollback()
        require(fingerprint(engine) == before, "Database differs after rollback")
        for check in checks:
            print("PASS=" + check)
        print("RESTORED_WALLET=PASS ROLLBACK_VERIFIED NO_PRODUCTION_CHANGES NO_COLLECTION_WORKER")
        return 0
    except Exception as error:
        print(f"RESTORED_WALLET=FAILED TYPE={type(error).__name__}; no production fallback")
        return 1
    finally:
        if engine is not None:
            engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
