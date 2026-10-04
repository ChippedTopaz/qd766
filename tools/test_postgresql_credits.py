"""Offline concurrency checks in qd766_credit_test only; never use production DB."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys
from threading import Barrier
import uuid
from unittest.mock import patch

from sqlalchemy import create_engine, func, select, text
from sqlalchemy.engine import URL, make_url
from sqlalchemy.orm import sessionmaker

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from qd766.backend.models import Base, CollectionControl, CollectionJob, CreditLedgerEntry, Department, Formality, PaidDataRequest, Snapshot, UserAccount, UserNotification
from qd766.backend.paid_requests import create_paid_data_request, refund_paid_requests_for_job, settle_paid_requests_for_job, top_up_credits, PendingRequestLimit
from qd766.backend.local_credit_trial import mock_snapshot
from qd766.backend import worker

TEST_DATABASE = "qd766_credit_test"


def isolated_url(path):
    values = {}
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        key, separator, value = line.strip().partition("=")
        if separator and not key.startswith("#"):
            values[key] = value
    if values.get("QD766_DATABASE_URL"):
        source = make_url(values["QD766_DATABASE_URL"])
        url = URL.create("postgresql+psycopg", username=source.username, password=source.password,
                         host=source.host, port=source.port, database=TEST_DATABASE)
    else:
        url = URL.create("postgresql+psycopg", username=values.get("QD766_DATABASE_USER", "qd766_app"),
                         password=values.get("QD766_DATABASE_PASSWORD"),
                         host=values.get("QD766_DATABASE_HOST", "127.0.0.1"),
                         port=int(values.get("QD766_DATABASE_PORT", "5432")), database=TEST_DATABASE)
    if url.host not in {"127.0.0.1", "localhost", "::1"}:
        raise ValueError("Only loopback PostgreSQL is allowed")
    return url


def provision(url):
    # Connect to maintenance DB, not the configured application database.
    engine = create_engine(url.set(database="postgres"), isolation_level="AUTOCOMMIT",
                           connect_args={"connect_timeout": 5})
    try:
        with engine.connect() as connection:
            exists = connection.scalar(text("SELECT 1 FROM pg_database WHERE datname=:name"), {"name": TEST_DATABASE})
            if not exists:
                connection.execute(text('CREATE DATABASE "qd766_credit_test"'))
                print("TEST_DATABASE_CREATED=qd766_credit_test", flush=True)
    finally:
        engine.dispose()


def run_checks(url):
    if url.database != TEST_DATABASE:
        raise ValueError("Refusing non-test database")
    schema = "credit_run_" + datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_") + uuid.uuid4().hex[:8]
    engine = create_engine(url, connect_args={"connect_timeout": 5}, pool_size=8, max_overflow=0)
    try:
        with engine.begin() as connection:
            connection.execute(text(f'CREATE SCHEMA "{schema}"'))
    finally:
        engine.dispose()
    engine = create_engine(url, connect_args={"connect_timeout": 5,
        "options": f"-c search_path={schema} -c lock_timeout=10000 -c statement_timeout=20000"},
        pool_size=8, max_overflow=0)
    factory = sessionmaker(engine, expire_on_commit=False)
    print(f"TEST_SCHEMA={schema} (retained for inspection)", flush=True)
    try:
        Base.metadata.create_all(engine)
        root, formality = uuid.uuid4(), uuid.uuid4()
        accounts = [uuid.uuid4() for _ in range(6)]
        with factory.begin() as db:
            db.add(Department(id=root, name="Tỉnh mô phỏng PostgreSQL", attributes={}))
            db.add(Formality(id=formality, code="PG.TEST", name="TTHC mô phỏng", attributes={}))
            for i, account in enumerate(accounts):
                db.add(UserAccount(id=account, external_subject=f"pg-test:{i}", display_name=f"PG {i}", plan="paid"))
            db.flush()
            for i, account in enumerate(accounts):
                top_up_credits(db, account, 30, event_key=f"seed:{i}")

        def parallel(month, *, same_account=False, same_token=False):
            barrier = Barrier(6)
            def submit(i):
                barrier.wait(timeout=15)
                with factory.begin() as db:
                    paid, _ = create_paid_data_request(db, account_id=accounts[0 if same_account else i],
                        province_code="25", root_department_id=root, formality_id=formality,
                        period_type="month", year=2026, period_value=month, credit_cost=3,
                        idempotency_token=f"month:{month}:" + ("repeat" if same_token else str(i)))
                    return paid.id, paid.collection_job_id
            with ThreadPoolExecutor(max_workers=6) as executor:
                return list(executor.map(submit, range(6)))

        def job_count(db):
            return db.scalar(select(func.count()).select_from(CollectionJob))

        def finish(job_id, success):
            with factory.begin() as db:
                job = db.get(CollectionJob, job_id)
                if success:
                    period = job.request["period"]
                    snapshot = Snapshot(snapshot_key=f"pg-test:{job.id}", schema_version=1,
                        root_department_id=root, period_type="month", year=2026,
                        period_value=period["month"], scope="formality", formality_id=formality,
                        state="complete", policy={"simulation": True}, status_detail={})
                    db.add(snapshot); db.flush()
                    settle_paid_requests_for_job(db, job, snapshot)
                    job.state = "succeeded"
                else:
                    job.state = "failed"
                    refund_paid_requests_for_job(db, job, {"kind": "pg-test-failure"})

        first = parallel(1)
        assert len({r[0] for r in first}) == 6 and len({r[1] for r in first}) == 1
        with factory() as db:
            assert job_count(db) == 1
            assert all((db.get(UserAccount, a).credit_balance, db.get(UserAccount, a).credit_reserved) == (27, 3) for a in accounts)
        finish(first[0][1], True)
        print("PASS=6_accounts_share_job_and_pay_separately", flush=True)

        # Several clicks with different tokens must still buy the dataset once.
        repeated = parallel(2, same_account=True)
        assert len({r[0] for r in repeated}) == 1
        finish(repeated[0][1], True)
        replay = parallel(2, same_account=True, same_token=True)
        assert len({r[0] for r in replay}) == 1 and replay[0][0] == repeated[0][0]
        with factory() as db:
            account = db.get(UserAccount, accounts[0])
            assert (account.credit_balance, account.credit_reserved) == (24, 0)
            assert job_count(db) == 2
        print("PASS=same_account_concurrent_confirmations_charge_once", flush=True)

        failed = parallel(3)
        finish(failed[0][1], False)
        retried = parallel(3)
        # Use fresh confirmation tokens after refund, not the original replay.
        assert all(r[0] == old[0] for r, old in zip(retried, failed))
        assert all(r[1] == failed[0][1] for r in retried)
        print("PASS=old_confirmation_replay_does_not_retry", flush=True)

        barrier = Barrier(6)
        def retry(i):
            barrier.wait(timeout=15)
            with factory.begin() as db:
                paid, _ = create_paid_data_request(db, account_id=accounts[i], province_code="25",
                    root_department_id=root, formality_id=formality, period_type="month", year=2026,
                    period_value=3, credit_cost=3, idempotency_token=f"fresh-retry:{i}")
                return paid.id, paid.collection_job_id
        with ThreadPoolExecutor(max_workers=6) as executor:
            successors = list(executor.map(retry, range(6)))
        assert len({r[1] for r in successors}) == 1 and successors[0][1] != failed[0][1]
        finish(successors[0][1], True)
        with factory() as db:
            assert job_count(db) == 4
            assert db.scalar(select(func.count()).select_from(PaidDataRequest).where(PaidDataRequest.state == "refunded")) == 6
            assert db.scalar(select(func.count()).select_from(CreditLedgerEntry).where(CreditLedgerEntry.entry_type == "charge")) == 13
            for i, a in enumerate(accounts):
                account = db.get(UserAccount, a)
                assert (account.credit_balance, account.credit_reserved) == (21 if i == 0 else 24, 0)
        print("PASS=concurrent_retry_preserves_refunds_and_shares_new_job", flush=True)

        class SimulatedWorkerCrash(BaseException):
            """Abrupt stop: bypass worker's normal exception/retry handler."""

        def processor(job_id, request):
            snapshot = mock_snapshot(request)
            for dataset in snapshot["datasets"]:
                dataset["root"]["departmentId"] = str(root)
            return snapshot

        def expire_crashed_lease(job_id):
            # Advance only test DB lease timestamps, not wall clock or production.
            with factory.begin() as db:
                expired = datetime.now(timezone.utc) - timedelta(seconds=120)
                db.get(CollectionJob, job_id).locked_at = expired
                db.get(CollectionControl, "dvcqg").lease_locked_at = expired

        def count(db, model, *conditions):
            return db.scalar(select(func.count()).select_from(model).where(*conditions))

        def assert_holds(month, expected_snapshots):
            with factory() as db:
                assert count(db, Snapshot, Snapshot.period_value == month) == expected_snapshots
                assert count(db, CreditLedgerEntry, CreditLedgerEntry.entry_type == "charge") == (19 if month == 5 else 13)
                for i, a in enumerate(accounts):
                    account = db.get(UserAccount, a)
                    balance = (15 if i == 0 else 18) if month == 5 else (18 if i == 0 else 21)
                    assert (account.credit_balance, account.credit_reserved) == (balance, 3)

        interrupted = parallel(4)
        def stop_while_collecting(job_id, request):
            raise SimulatedWorkerCrash()
        try:
            worker.run_one_job(factory, stop_while_collecting, worker_id="test-crashed-collector", lease_seconds=60)
            raise AssertionError("Expected simulated crash")
        except SimulatedWorkerCrash:
            pass
        assert_holds(4, 0)
        blocked = worker.run_one_job(factory, processor, worker_id="test-recovery", lease_seconds=60)
        assert blocked.state == "busy"
        expire_crashed_lease(interrupted[0][1])
        recovered = worker.run_one_job(factory, processor, worker_id="test-recovery", lease_seconds=60)
        assert recovered.state == "succeeded" and recovered.job_id == interrupted[0][1]
        with factory() as db:
            assert count(db, Snapshot, Snapshot.period_value == 4) == 1
            assert count(db, PaidDataRequest, PaidDataRequest.collection_job_id == recovered.job_id,
                         PaidDataRequest.state == "ready") == 6
            assert db.get(CollectionJob, recovered.job_id).attempts == 2
        print("PASS=crash_during_collection_holds_credit_then_recovers_after_lease", flush=True)

        interrupted = parallel(5)
        real_settle = worker.settle_paid_requests_for_job
        def stop_after_settlement(db, job, snapshot):
            real_settle(db, job, snapshot)
            # Snapshot, ledger and notifications are flushed but not committed.
            db.flush()
            raise SimulatedWorkerCrash()
        with patch.object(worker, "settle_paid_requests_for_job", stop_after_settlement):
            try:
                worker.run_one_job(factory, processor, worker_id="test-crashed-writer", lease_seconds=60)
                raise AssertionError("Expected simulated crash")
            except SimulatedWorkerCrash:
                pass
        assert_holds(5, 0)
        with factory() as db:
            assert count(db, UserNotification) == 25  # 19 success + 6 prior refunds
        expire_crashed_lease(interrupted[0][1])
        recovered = worker.run_one_job(factory, processor, worker_id="test-recovered-writer", lease_seconds=60)
        assert recovered.state == "succeeded" and recovered.job_id == interrupted[0][1]
        with factory() as db:
            assert count(db, Snapshot, Snapshot.period_value == 5) == 1
            assert count(db, CreditLedgerEntry, CreditLedgerEntry.entry_type == "charge") == 25
            assert count(db, UserNotification) == 31
            for i, a in enumerate(accounts):
                account = db.get(UserAccount, a)
                assert (account.credit_balance, account.credit_reserved) == (15 if i == 0 else 18, 0)
        print("PASS=crash_before_commit_rolls_back_snapshot_credits_notifications", flush=True)

        # The completed result is intentionally discarded, like an acknowledgement
        # lost after commit. Restarting a worker must not process/charge it again.
        assert worker.run_one_job(factory, processor, worker_id="test-after-lost-ack", lease_seconds=60) is None
        with factory() as db:
            assert job_count(db) == 6
            assert count(db, CreditLedgerEntry, CreditLedgerEntry.entry_type == "charge") == 25
            assert count(db, UserNotification) == 31
        print("PASS=restart_after_committed_success_does_not_charge_twice", flush=True)
        limited_account=uuid.uuid4()
        with factory.begin() as db:
            db.add(UserAccount(id=limited_account,external_subject="pg-limit-test",display_name="Limit test",plan="paid"))
            db.flush()
            top_up_credits(db,limited_account,30,event_key="seed:limit")
        barrier=Barrier(6)
        def submit_limited(i):
            barrier.wait(timeout=15)
            try:
                with factory.begin() as db:
                    create_paid_data_request(db,account_id=limited_account,province_code="25",
                        root_department_id=root,formality_id=formality,period_type="month",year=2025,
                        period_value=7+i,credit_cost=3,idempotency_token=f"limited:{i}",max_pending_requests=2)
                return "accepted"
            except PendingRequestLimit:
                return "limited"
        with ThreadPoolExecutor(max_workers=6) as executor:
            outcomes=list(executor.map(submit_limited,range(6)))
        assert outcomes.count("accepted")==2 and outcomes.count("limited")==4
        with factory() as db:
            assert count(db,PaidDataRequest,PaidDataRequest.account_id==limited_account)==2
            assert count(db,CreditLedgerEntry,CreditLedgerEntry.account_id==limited_account,
                         CreditLedgerEntry.entry_type=="reserve")==2
            account=db.get(UserAccount,limited_account)
            assert (account.credit_balance,account.credit_reserved)==(24,6)
        print("PASS=six_concurrent_distinct_requests_accept_two_without_extra_holds",flush=True)
        from qd766.backend.credit_wallet import grant,reserve,balance,WalletError
        wallet_account=uuid.uuid4()
        wallet_now=datetime.now(timezone.utc)
        with factory.begin() as db:
            db.add(UserAccount(id=wallet_account,external_subject="pg-wallet-test",display_name="Wallet concurrency",plan="paid"))
            db.flush()
            grant(db,wallet_account,10,source="purchased",operation_key="seed",now=wallet_now)
        wallet_barrier=Barrier(6)
        def reserve_wallet(i):
            wallet_barrier.wait(timeout=15)
            try:
                with factory.begin() as db:
                    reserve(db,wallet_account,5,request_key=f"wallet:{i}",now=wallet_now)
                return "held"
            except WalletError:
                return "insufficient"
        with ThreadPoolExecutor(max_workers=6) as executor:
            results=list(executor.map(reserve_wallet,range(6)))
        assert results.count("held")==2 and results.count("insufficient")==4
        with factory() as db:
            assert balance(db,wallet_account,now=wallet_now)==dict(subscription=0,purchased=0,reserved=10,available=0)
        print("PASS=source_wallet_concurrent_reservations_never_overspend",flush=True)
        from qd766.backend.subscriptions import redeem_month,schedule_plan,grant_due_cycles,monthly_boundary
        from qd766.backend.models import SubscriptionCycle,CreditWalletEvent
        subscription_account=uuid.uuid4()
        with factory.begin() as db:
            db.add(UserAccount(id=subscription_account,external_subject="pg-subscription-test",
                display_name="Subscription concurrency",access_tier="province"))
            db.flush()
            grant(db,subscription_account,1000,source="purchased",operation_key="seed",now=wallet_now)
        redemption_barrier=Barrier(6)
        def redeem_concurrently(i):
            redemption_barrier.wait(timeout=15)
            try:
                with factory.begin() as db:
                    redeem_month(db,subscription_account,operation_key=f"redeem:{i}",now=wallet_now)
                return "redeemed"
            except WalletError:
                return "blocked"
        with ThreadPoolExecutor(max_workers=6) as executor:
            results=list(executor.map(redeem_concurrently,range(6)))
        assert results.count("redeemed")==1 and results.count("blocked")==5
        with factory() as db:
            assert balance(db,subscription_account,now=wallet_now)["purchased"]==400
            assert count(db,SubscriptionCycle,SubscriptionCycle.account_id==subscription_account)==1
            assert count(db,CreditWalletEvent,CreditWalletEvent.account_id==subscription_account,
                         CreditWalletEvent.kind=="charge")==1
        print("PASS=concurrent_subscription_redemption_charges_once",flush=True)
        cycle_now=monthly_boundary(wallet_now,1)
        with factory.begin() as db:
            schedule_plan(db,subscription_account,tier="province",origin="paid",operation_key="six-month-plan",
                          starts_at=cycle_now,months=6,now=wallet_now)
        grant_barrier=Barrier(6)
        def grant_concurrently(i):
            grant_barrier.wait(timeout=15)
            with factory.begin() as db:
                return grant_due_cycles(db,subscription_account,now=cycle_now)
        with ThreadPoolExecutor(max_workers=6) as executor:
            results=list(executor.map(grant_concurrently,range(6)))
        assert sum(results)==1
        with factory() as db:
            assert balance(db,subscription_account,now=cycle_now)==dict(subscription=200,purchased=400,reserved=0,available=600)
        print("PASS=concurrent_monthly_credit_grant_once_no_future_grants",flush=True)
        from qd766.backend.wallet_access import enroll
        factory.configure(info={"source_wallet_enabled":True})
        source_accounts=[uuid.uuid4(),uuid.uuid4()]
        with factory.begin() as db:
            for i,aid in enumerate(source_accounts):
                db.add(UserAccount(id=aid,external_subject=f"pg-source-request:{i}",display_name="Source request",
                    access_tier="province",plan="paid",credit_balance=31))
                db.flush();enroll(db,aid,now=wallet_now)
                grant(db,aid,2,source="subscription",operation_key="sub",now=wallet_now,
                      expires_at=monthly_boundary(wallet_now,1))
                grant(db,aid,10,source="purchased",operation_key="purchase",now=wallet_now)
                db.add(SubscriptionCycle(account_id=aid,operation_key="fixture",tier="province",
                    origin="redemption",starts_at=wallet_now,ends_at=monthly_boundary(wallet_now,1),included_credit=0))
        source_barrier=Barrier(6)
        def source_request(i):
            source_barrier.wait(timeout=15)
            with factory.begin() as db:
                paid,_=create_paid_data_request(db,account_id=source_accounts[i%2],province_code="25",
                    root_department_id=root,formality_id=formality,period_type="month",year=2026,
                    period_value=9,credit_cost=5,idempotency_token=f"source:{i}",max_pending_requests=2)
                return paid.id,paid.collection_job_id
        with ThreadPoolExecutor(max_workers=6) as executor:
            results=list(executor.map(source_request,range(6)))
        assert len({r[0] for r in results})==2 and len({r[1] for r in results})==1
        finish(results[0][1],True)
        with factory() as db:
            for aid in source_accounts:
                assert balance(db,aid,now=wallet_now)==dict(subscription=0,purchased=7,reserved=0,available=7)
                assert (db.get(UserAccount,aid).credit_balance,db.get(UserAccount,aid).credit_reserved)==(31,0)
                assert count(db,CreditWalletEvent,CreditWalletEvent.account_id==aid,CreditWalletEvent.kind=="charge")==1
        print("PASS=source_wallet_shared_job_separate_charges_no_legacy_mutation",flush=True)
        activation_account=uuid.uuid4()
        with factory.begin() as db:
            db.add(UserAccount(id=activation_account,external_subject="pg-trial-activation",
                display_name="Trial activation",access_tier="province",trial_admitted=True,credit_balance=50))
        activation_barrier=Barrier(6)
        def activate_concurrently(i):
            activation_barrier.wait(timeout=15)
            try:
                with factory.begin() as db:
                    enroll(db,activation_account,now=wallet_now)
                    schedule_plan(db,activation_account,tier="province",origin="trial",
                        operation_key=f"trial:{i}",starts_at=wallet_now,months=1,now=wallet_now)
                    grant_due_cycles(db,activation_account,now=wallet_now)
                return "activated"
            except WalletError:
                return "blocked"
        with ThreadPoolExecutor(max_workers=6) as executor:
            results=list(executor.map(activate_concurrently,range(6)))
        assert results.count("activated")==1 and results.count("blocked")==5
        with factory() as db:
            assert balance(db,activation_account,now=wallet_now)["subscription"]==100
            assert db.get(UserAccount,activation_account).credit_balance==50
            assert count(db,SubscriptionCycle,SubscriptionCycle.account_id==activation_account)==1
        print("PASS=concurrent_trial_activation_grants_one_free_month_once",flush=True)
        from qd766.backend.subscription_maintenance import run_subscription_maintenance
        maintenance_account = uuid.uuid4()
        with factory.begin() as db:
            db.add(UserAccount(id=maintenance_account, external_subject="pg-cycle-maintenance",
                display_name="Maintenance", access_tier="agency", root_department_id=root,
                unit_department_id=root, credit_balance=63))
            db.flush()
            enroll(db, maintenance_account, now=wallet_now)
            schedule_plan(db, maintenance_account, tier="agency", origin="paid",
                operation_key="maintenance-fixture", starts_at=wallet_now, months=6, now=wallet_now)
        maintenance_barrier = Barrier(6)
        def maintain_concurrently(i):
            maintenance_barrier.wait(timeout=15)
            return run_subscription_maintenance(factory, now=wallet_now, batch_size=2)
        with ThreadPoolExecutor(max_workers=6) as executor:
            maintenance_results = list(executor.map(maintain_concurrently, range(6)))
        assert all(not result["failures"] for result in maintenance_results)
        with factory() as db:
            assert balance(db, maintenance_account, now=wallet_now)["subscription"] == 100
            assert db.get(UserAccount, maintenance_account).credit_balance == 63
            assert count(db, CreditWalletEvent, CreditWalletEvent.account_id==maintenance_account,
                         CreditWalletEvent.kind=="grant") == 1
        print("PASS=overlapping_maintenance_runs_grant_current_cycle_once", flush=True)
        print("POSTGRESQL_CREDIT_TEST=PASS NO_DVCQG_CALLS NO_PRODUCTION_DB", flush=True)
    finally:
        engine.dispose()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--connection-file", type=Path, required=True,
                        help="Read host/user/password only; database is always qd766_credit_test")
    parser.add_argument("--create-test-database", action="store_true")
    args = parser.parse_args()
    try:
        url = isolated_url(args.connection_file)
        if args.create_test_database:
            provision(url)
        run_checks(url)
    except Exception as error:
        # Never print URLs/credentials or SQL parameter dumps.
        print(f"POSTGRESQL_CREDIT_TEST=FAIL TYPE={type(error).__name__}", flush=True)
        original = getattr(error, "orig", None)
        state = getattr(original, "sqlstate", None)
        if state:
            print(f"POSTGRESQL_SQLSTATE={state}", flush=True)
        if state == "42501":
            print("TEST_DATABASE_PERMISSION_REQUIRED=Create qd766_credit_test owned by the application role.")
        print("Check test database permission/connectivity. No production fallback or cleanup was attempted.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
