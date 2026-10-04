import sys
import unittest
import uuid
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from sqlalchemy import func, select
from qd766.backend.config import Settings
from qd766.backend.database import create_database_engine, create_session_factory
from qd766.backend.models import Base, CreditWalletEvent, Department, UserAccount
from qd766.backend.credit_wallet import WalletError, balance, grant, reserve
from qd766.backend.wallet_access import enroll
from qd766.backend.subscriptions import grant_due_cycles, monthly_boundary, schedule_plan
from qd766.backend.subscription_maintenance import run_subscription_maintenance


class MaintenanceTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_database_engine(Settings(database_url="sqlite+pysqlite://"))
        Base.metadata.create_all(self.engine)
        self.factory = create_session_factory(self.engine)
        self.factory.configure(info={"source_wallet_enabled": True})
        self.now = datetime(2026, 1, 31, 12, tzinfo=timezone.utc)
        self.unit = uuid.uuid4()
        with self.factory.begin() as db:
            db.add(Department(id=self.unit, name="Test unit", attributes={}))

    def tearDown(self):
        self.engine.dispose()

    def account(self, *, opted_in=True, active=True, start=None):
        account_id = uuid.uuid4()
        with self.factory.begin() as db:
            db.add(UserAccount(id=account_id, external_subject=str(account_id),
                display_name="Test", access_tier="agency", root_department_id=self.unit,
                unit_department_id=self.unit, active=active, credit_balance=77))
            db.flush()
            if opted_in:
                enroll(db, account_id, now=self.now)
            schedule_plan(db, account_id, tier="agency", origin="paid",
                operation_key="fixture", starts_at=start or self.now, months=6, now=self.now)
        return account_id

    def run_at(self, now=None, **kwargs):
        return run_subscription_maintenance(self.factory, now=now or self.now, **kwargs)

    def test_requires_explicit_source_wallet_flag_and_valid_batch(self):
        self.account()
        self.factory.configure(info={})
        with self.assertRaises(WalletError):
            self.run_at()
        self.factory.configure(info={"source_wallet_enabled": True})
        for value in (0, 1001, True):
            with self.assertRaises(WalletError):
                self.run_at(batch_size=value)
        with self.factory() as db:
            self.assertEqual(db.scalar(select(func.count()).select_from(CreditWalletEvent)), 0)

    def test_paged_replay_grants_once_and_skips_unenrolled_accounts(self):
        ids = [self.account() for _ in range(3)]
        legacy = self.account(opted_in=False)
        first = self.run_at(batch_size=1)
        self.assertEqual((first["processed"], first["grantedCycles"], first["failures"]), (3, 3, []))
        self.assertEqual(self.run_at(batch_size=2)["grantedCycles"], 0)
        with self.factory() as db:
            for account_id in ids:
                self.assertEqual(balance(db, account_id, now=self.now)["subscription"], 100)
                self.assertEqual(db.get(UserAccount, account_id).credit_balance, 77)
            self.assertEqual(balance(db, legacy, now=self.now)["available"], 0)

    def test_month_transition_keeps_holds_and_purchased_credit(self):
        account_id = self.account()
        self.run_at()
        with self.factory.begin() as db:
            grant(db, account_id, 600, source="purchased", operation_key="fixture", now=self.now)
            reserve(db, account_id, 5, request_key="pending", now=self.now)
        next_month = monthly_boundary(self.now, 1)
        result = self.run_at(next_month)
        self.assertEqual((result["grantedCycles"], result["expiredCredit"]), (1, 95))
        self.assertEqual(self.run_at(next_month)["expiredCredit"], 0)
        with self.factory() as db:
            self.assertEqual(balance(db, account_id, now=next_month),
                dict(subscription=100, purchased=600, reserved=5, available=700))

    def test_failed_account_rolls_back_and_other_accounts_continue(self):
        ids = [self.account() for _ in range(3)]
        failed = ids[0]

        def fail_after_grant(db, account_id, *, now):
            count = grant_due_cycles(db, account_id, now=now)
            if account_id == failed:
                raise RuntimeError("private diagnostic must not leak")
            return count

        with patch("qd766.backend.subscription_maintenance.grant_due_cycles", side_effect=fail_after_grant):
            result = self.run_at(batch_size=1)
        self.assertEqual(result["processed"], 2)
        self.assertEqual(result["grantedCycles"], 2)
        self.assertEqual(result["failures"], [{"accountId": str(failed), "type": "RuntimeError"}])
        with self.factory() as db:
            self.assertEqual(balance(db, failed, now=self.now)["available"], 0)
        retry = self.run_at()
        self.assertEqual((retry["grantedCycles"], retry["failures"]), (1, []))

    def test_future_cycles_not_granted_and_late_run_only_grants_current_month(self):
        future = self.account(start=monthly_boundary(self.now, 1))
        current = self.account()
        self.assertEqual(self.run_at()["grantedCycles"], 1)
        later = monthly_boundary(self.now, 3)
        self.assertEqual(self.run_at(later)["grantedCycles"], 2)
        with self.factory() as db:
            for account_id in (future, current):
                self.assertEqual(balance(db, account_id, now=later)["subscription"], 100)
        ended = monthly_boundary(self.now, 8)
        self.assertEqual(self.run_at(ended)["grantedCycles"], 0)
        with self.factory() as db:
            self.assertEqual(balance(db, current, now=ended)["subscription"], 0)

    def test_maintenance_never_reactivates_locked_account_or_creates_trial(self):
        account_id = self.account(active=False)
        self.run_at()
        with self.factory() as db:
            self.assertFalse(db.get(UserAccount, account_id).active)
            self.assertEqual(db.get(UserAccount, account_id).credit_balance, 77)
            self.assertFalse(db.get(UserAccount, account_id).trial_admitted)


if __name__ == "__main__":
    unittest.main()
