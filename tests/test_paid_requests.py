import sys
import unittest
import uuid
from pathlib import Path

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from qd766.backend.models import (
    Base,
    CollectionJob,
    CreditLedgerEntry,
    Department,
    Formality,
    PaidDataRequest,
    Snapshot,
    UserAccount,
    UserNotification,
)
from qd766.backend.paid_requests import (
    InsufficientCredits,
    PaidPlanRequired,
    create_paid_data_request,
    refund_paid_requests_for_job,
    settle_paid_requests_for_job,
    top_up_credits,
)
from qd766.backend.worker import run_one_job
from qd766.collection import SafetyStop


class PaidRequestTest(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite+pysqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(self.engine)
        self.factory = sessionmaker(bind=self.engine, expire_on_commit=False)
        self.root_id = uuid.uuid4()
        self.formality_id = uuid.uuid4()
        self.account_ids = [uuid.uuid4() for _ in range(4)]
        with self.factory.begin() as session:
            session.add(
                Department(
                    id=self.root_id,
                    code="H44",
                    name="UBND tỉnh Phú Thọ",
                    attributes={},
                )
            )
            session.add(
                Formality(
                    id=self.formality_id,
                    code="2.000815",
                    name="Thủ tục kiểm thử",
                    attributes={},
                )
            )
            for index, account_id in enumerate(self.account_ids):
                session.add(
                    UserAccount(
                        id=account_id,
                        external_subject=f"test-{index}",
                        display_name=f"Tài khoản {index}",
                        plan="free" if index == 3 else "paid",
                    )
                )
            for index, account_id in enumerate(self.account_ids[:3]):
                top_up_credits(
                    session,
                    account_id,
                    10,
                    event_key=f"topup-{index}",
                )

    def tearDown(self):
        self.engine.dispose()

    def _request(self, session, account_index, token, **overrides):
        values = {
            "account_id": self.account_ids[account_index],
            "province_code": "25",
            "root_department_id": self.root_id,
            "formality_id": self.formality_id,
            "period_type": "year",
            "year": 2026,
            "period_value": None,
            "credit_cost": 3,
            "idempotency_token": token,
        }
        values.update(overrides)
        return create_paid_data_request(session, **values)

    def _snapshot(self, session, suffix="year"):
        snapshot = Snapshot(
            snapshot_key=f"paid-test-{suffix}",
            schema_version=1,
            root_department_id=self.root_id,
            period_type="year",
            year=2026,
            period_value=None,
            scope="formality",
            formality_id=self.formality_id,
            state="complete",
            policy={},
            status_detail={},
        )
        session.add(snapshot)
        session.flush()
        return snapshot

    def test_two_accounts_pay_separately_but_share_one_collection_job(self):
        with self.factory.begin() as session:
            first, first_created = self._request(session, 0, "first")
            second, second_created = self._request(session, 1, "second")
            self.assertTrue(first_created)
            self.assertTrue(second_created)
            self.assertEqual(first.state, "waiting")
            self.assertEqual(second.state, "waiting")
            self.assertEqual(first.collection_job_id, second.collection_job_id)
            self.assertEqual(
                session.scalar(select(func.count()).select_from(CollectionJob)), 1
            )
            for account_id in self.account_ids[:2]:
                account = session.get(UserAccount, account_id)
                self.assertEqual((account.credit_balance, account.credit_reserved), (7, 3))

            job = session.get(CollectionJob, first.collection_job_id)
            snapshot = self._snapshot(session)
            self.assertEqual(settle_paid_requests_for_job(session, job, snapshot), 2)

        with self.factory() as session:
            requests = list(session.scalars(select(PaidDataRequest)))
            self.assertEqual({item.state for item in requests}, {"ready"})
            self.assertTrue(all(item.snapshot_id is not None for item in requests))
            for account_id in self.account_ids[:2]:
                account = session.get(UserAccount, account_id)
                self.assertEqual((account.credit_balance, account.credit_reserved), (7, 0))
            self.assertEqual(
                session.scalar(select(func.count()).select_from(UserNotification)), 2
            )
            self.assertEqual(
                session.scalar(
                    select(func.count())
                    .select_from(CreditLedgerEntry)
                    .where(CreditLedgerEntry.entry_type == "charge")
                ),
                2,
            )

    def test_cached_data_still_charges_but_does_not_create_job(self):
        with self.factory.begin() as session:
            snapshot = self._snapshot(session)
            paid_request, created = self._request(session, 2, "cached")
            self.assertTrue(created)
            self.assertEqual(paid_request.state, "ready")
            self.assertEqual(paid_request.snapshot_id, snapshot.id)
            self.assertIsNone(paid_request.collection_job_id)
            account = session.get(UserAccount, self.account_ids[2])
            self.assertEqual((account.credit_balance, account.credit_reserved), (7, 0))
            self.assertEqual(
                session.scalar(select(func.count()).select_from(CollectionJob)), 0
            )
            same, created = self._request(session, 2, "another-click")
            self.assertFalse(created)
            self.assertEqual(same.id, paid_request.id)
            self.assertEqual(account.credit_balance, 7)

    def test_terminal_failure_refunds_reserved_credit_and_notifies(self):
        with self.factory.begin() as session:
            paid_request, _ = self._request(session, 0, "will-fail")
            job = session.get(CollectionJob, paid_request.collection_job_id)
            refunded = refund_paid_requests_for_job(
                session, job, {"kind": "upstream-safety-stop"}
            )
            self.assertEqual(refunded, 1)
            self.assertEqual(paid_request.state, "refunded")
            account = session.get(UserAccount, self.account_ids[0])
            self.assertEqual((account.credit_balance, account.credit_reserved), (10, 0))
            notification = session.scalar(select(UserNotification))
            self.assertEqual(notification.kind, "data-failed")
            entries = list(
                session.scalars(
                    select(CreditLedgerEntry)
                    .where(CreditLedgerEntry.paid_request_id == paid_request.id)
                    .order_by(CreditLedgerEntry.created_at, CreditLedgerEntry.entry_type)
                )
            )
            self.assertEqual({entry.entry_type for entry in entries}, {"reserve", "release"})

    def test_worker_safety_stop_refunds_every_linked_paid_request(self):
        with self.factory.begin() as session:
            paid_request, _ = self._request(session, 0, "worker-stop")
            job_id = paid_request.collection_job_id

        def rejected_processor(job_id, request):
            raise SafetyStop("request rejected")

        result = run_one_job(
            self.factory,
            rejected_processor,
            worker_id="paid-test-worker",
        )
        self.assertEqual((result.job_id, result.state), (job_id, "halted"))
        with self.factory() as session:
            paid_request = session.scalar(
                select(PaidDataRequest).where(
                    PaidDataRequest.collection_job_id == job_id
                )
            )
            account = session.get(UserAccount, self.account_ids[0])
            self.assertEqual(paid_request.state, "refunded")
            self.assertEqual((account.credit_balance, account.credit_reserved), (10, 0))
            self.assertEqual(
                session.scalar(select(func.count()).select_from(UserNotification)), 1
            )

    def test_free_plan_and_insufficient_balance_are_rejected_without_charge(self):
        with self.factory.begin() as session:
            with self.assertRaises(PaidPlanRequired):
                self._request(session, 3, "free")
            with self.assertRaises(InsufficientCredits):
                self._request(session, 0, "too-expensive", credit_cost=11)
            self.assertEqual(
                session.scalar(select(func.count()).select_from(PaidDataRequest)), 0
            )


if __name__ == "__main__":
    unittest.main()
