import sys
import unittest
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from sqlalchemy import func, select
from qd766.backend.config import Settings
from qd766.backend.database import create_database_engine, create_session_factory
from qd766.backend.models import Base, CreditWalletEvent, Department, SubscriptionCycle, UserAccount
from qd766.backend.credit_wallet import WalletError, balance, grant, reserve
from qd766.backend.subscriptions import grant_due_cycles, monthly_boundary, redeem_month, schedule_plan


class SubscriptionTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_database_engine(Settings(database_url="sqlite+pysqlite://"))
        Base.metadata.create_all(self.engine)
        self.factory = create_session_factory(self.engine)
        self.account, self.unit = uuid.uuid4(), uuid.uuid4()
        self.now = datetime(2026, 1, 31, 23, 30, tzinfo=ZoneInfo("Asia/Ho_Chi_Minh"))
        with self.factory.begin() as db:
            db.add(Department(id=self.unit, name="Sở kiểm thử", attributes={}))
            db.flush()
            db.add(UserAccount(id=self.account, external_subject="subscriptions:test",
                display_name="Test", access_tier="agency", root_department_id=self.unit,
                unit_department_id=self.unit, credit_balance=99))

    def tearDown(self):
        self.engine.dispose()

    def plan(self, db, **kwargs):
        return schedule_plan(db, self.account, tier=kwargs.pop("tier", "agency"),
            origin=kwargs.pop("origin", "paid"), operation_key=kwargs.pop("operation_key", "paid-1"),
            starts_at=kwargs.pop("starts_at", self.now), months=kwargs.pop("months", 6),
            now=self.now, **kwargs)

    def test_calendar_uses_vietnam_and_restores_anchor_day(self):
        dates = [monthly_boundary(self.now, i).astimezone(ZoneInfo("Asia/Ho_Chi_Minh")) for i in range(4)]
        self.assertEqual([(v.month, v.day, v.hour, v.minute) for v in dates],
                         [(1,31,23,30),(2,28,23,30),(3,31,23,30),(4,30,23,30)])
        leap = self.now.replace(year=2028)
        self.assertEqual(monthly_boundary(leap,1).astimezone(ZoneInfo("Asia/Ho_Chi_Minh")).day,29)
        self.assertEqual(monthly_boundary(self.now,12).astimezone(ZoneInfo("Asia/Ho_Chi_Minh")).year,2027)

    def test_long_plan_grants_monthly_not_upfront_and_replay_is_free(self):
        with self.factory.begin() as db:
            cycles = self.plan(db)
            self.assertEqual(balance(db,self.account,now=self.now)["available"],0)
            self.assertEqual(grant_due_cycles(db,self.account,now=self.now),1)
            self.assertEqual(grant_due_cycles(db,self.account,now=self.now),0)
            self.assertEqual(balance(db,self.account,now=self.now)["subscription"],100)
            self.assertEqual([c.id for c in self.plan(db)], [c.id for c in cycles])
            next_month = monthly_boundary(self.now,1)
            self.assertEqual(grant_due_cycles(db,self.account,now=next_month),1)
            self.assertEqual(balance(db,self.account,now=next_month)["subscription"],100)
            self.assertEqual(db.scalar(select(func.count()).select_from(CreditWalletEvent)
                .where(CreditWalletEvent.kind=="expire")),1)
            self.assertEqual(db.get(UserAccount,self.account).credit_balance,99)

    def test_delayed_scheduler_skips_expired_and_future_months(self):
        with self.factory.begin() as db:
            self.plan(db, months=12, tier="province")
            later = monthly_boundary(self.now,3)
            self.assertEqual(grant_due_cycles(db,self.account,now=later),1)
            self.assertEqual(balance(db,self.account,now=later)["subscription"],200)
            self.assertEqual(grant_due_cycles(db,self.account,now=monthly_boundary(self.now,12)),0)
            self.assertEqual(balance(db,self.account,now=monthly_boundary(self.now,12))["available"],0)

    def test_trial_province_grants_100_once(self):
        with self.factory.begin() as db:
            self.plan(db, origin="trial", tier="province", months=1)
            grant_due_cycles(db,self.account,now=self.now)
            self.assertEqual(balance(db,self.account,now=self.now)["subscription"],100)
            with self.assertRaises(WalletError):
                self.plan(db, origin="trial", months=1, operation_key="trial-again",
                          starts_at=monthly_boundary(self.now,1))

    def test_unit_redemption_purchased_only_no_included_grant_and_idempotent(self):
        with self.factory.begin() as db:
            grant(db,self.account,1000,source="subscription",operation_key="bonus",now=self.now,
                  expires_at=monthly_boundary(self.now,1))
            grant(db,self.account,350,source="purchased",operation_key="purchase",now=self.now)
            cycle = redeem_month(db,self.account,operation_key="redeem",now=self.now)
            replay = redeem_month(db,self.account,operation_key="redeem",now=self.now+timedelta(days=1))
            self.assertEqual(cycle.id,replay.id)
            self.assertEqual(cycle.included_credit,0)
            self.assertEqual(grant_due_cycles(db,self.account,now=self.now),0)
            self.assertEqual(balance(db,self.account,now=self.now),
                             dict(subscription=1000,purchased=50,reserved=0,available=1050))
            with self.assertRaises(WalletError):
                redeem_month(db,self.account,operation_key="another",now=self.now)

    def test_province_cost_600_and_national_cannot_redeem(self):
        with self.factory.begin() as db:
            account = db.get(UserAccount,self.account)
            account.access_tier = "province"
            db.flush()
            grant(db,self.account,650,source="purchased",operation_key="purchase",now=self.now)
            redeem_month(db,self.account,operation_key="redeem",now=self.now)
            self.assertEqual(balance(db,self.account,now=self.now)["purchased"],50)
            account.access_tier="national"
            db.flush()
            with self.assertRaises(WalletError):
                redeem_month(db,self.account,operation_key="national",now=monthly_boundary(self.now,1))

    def test_insufficient_or_reserved_purchase_cannot_be_redeemed(self):
        with self.factory.begin() as db:
            grant(db,self.account,1000,source="subscription",operation_key="sub",now=self.now,
                  expires_at=monthly_boundary(self.now,1))
            with self.assertRaises(WalletError):
                redeem_month(db,self.account,operation_key="empty",now=self.now)
            grant(db,self.account,300,source="purchased",operation_key="buy",now=self.now)
            reserve(db,self.account,1005,request_key="held",now=self.now)
            with self.assertRaises(WalletError):
                redeem_month(db,self.account,operation_key="reserved",now=self.now)
            self.assertEqual(db.scalar(select(func.count()).select_from(SubscriptionCycle)),0)

    def test_overlap_duration_change_and_transaction_rollback(self):
        with self.factory.begin() as db:
            self.plan(db)
            with self.assertRaises(WalletError): self.plan(db,months=12)
            with self.assertRaises(WalletError): self.plan(db,operation_key="overlap")
        with self.assertRaises(RuntimeError):
            with self.factory.begin() as db:
                grant_due_cycles(db,self.account,now=self.now)
                raise RuntimeError("Crash")
        with self.factory() as db:
            self.assertEqual(balance(db,self.account,now=self.now)["available"],0)
            self.assertEqual(db.scalar(select(func.count()).select_from(CreditWalletEvent)),0)

    def test_admin_projection_is_read_only_and_distinguishes_expired_and_scheduled(self):
        from qd766.backend.wallet_access import enroll,subscription_summary
        self.factory.configure(info={"source_wallet_enabled":True})
        with self.factory.begin() as db:
            enroll(db,self.account,now=self.now)
            account=db.get(UserAccount,self.account)
            self.assertEqual(subscription_summary(db,account,now=self.now)["state"],"none")
            self.plan(db,months=1)
            self.assertEqual(subscription_summary(db,account,now=self.now-timedelta(seconds=1))["state"],"scheduled")
            summary=subscription_summary(db,account,now=self.now)
            self.assertEqual(summary["state"],"active")
            self.assertEqual(summary["subscriptionCredits"],0)
            self.assertEqual(subscription_summary(db,account,now=monthly_boundary(self.now,1))["state"],"expired")
            self.assertEqual(db.scalar(select(func.count()).select_from(CreditWalletEvent)),0)


if __name__ == "__main__": unittest.main()
