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
from qd766.backend.paid_requests import create_paid_data_request, refund_paid_requests_for_job, settle_paid_requests_for_job, top_up_credits
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
