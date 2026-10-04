import sys, unittest, uuid
from pathlib import Path
from datetime import datetime, timedelta, timezone
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"src"))
from sqlalchemy import select,func
from qd766.backend.config import Settings
from qd766.backend.database import create_database_engine,create_session_factory
from qd766.backend.models import Base,UserAccount,CreditLot,CreditWalletEvent
from qd766.backend.credit_wallet import grant,reserve,finish,expire,balance,WalletError


class CreditWalletTests(unittest.TestCase):
    def setUp(self):
        self.engine=create_database_engine(Settings(database_url="sqlite+pysqlite://"))
        Base.metadata.create_all(self.engine);self.factory=create_session_factory(self.engine)
        self.account=uuid.uuid4();self.other=uuid.uuid4()
        self.now=datetime(2026,10,4,tzinfo=timezone.utc)
        with self.factory.begin() as db:
            db.add_all([UserAccount(id=self.account,external_subject="wallet:a",display_name="A",credit_balance=99),
                        UserAccount(id=self.other,external_subject="wallet:b",display_name="B")])
    def tearDown(self):self.engine.dispose()
    def seed(self,db):
        grant(db,self.account,3,source="subscription",operation_key="cycle",now=self.now,expires_at=self.now+timedelta(days=1))
        grant(db,self.account,10,source="purchased",operation_key="purchase",now=self.now)

    def test_source_priority_hold_charge_and_no_legacy_mutation(self):
        with self.factory.begin() as db:
            self.seed(db)
            hold=reserve(db,self.account,5,request_key="request",now=self.now)
            self.assertEqual([(a["source"],a["amount"]) for a in hold.allocations],[("subscription",3),("purchased",2)])
            self.assertEqual(balance(db,self.account,now=self.now),dict(subscription=0,purchased=8,reserved=5,available=8))
            finish(db,self.account,request_key="request",outcome="charge",now=self.now+timedelta(days=2))
            finish(db,self.account,request_key="request",outcome="charge",now=self.now+timedelta(days=3))
            self.assertEqual(balance(db,self.account,now=self.now+timedelta(days=2))["reserved"],0)
            self.assertEqual(db.get(UserAccount,self.account).credit_balance,99)
            self.assertEqual(db.scalar(select(func.count()).select_from(CreditWalletEvent).where(CreditWalletEvent.kind=="charge")),1)

    def test_expired_subscription_refund_gets_seven_days_and_purchase_persists(self):
        with self.factory.begin() as db:
            self.seed(db);reserve(db,self.account,5,request_key="request",now=self.now)
            refunded=self.now+timedelta(days=2)
            finish(db,self.account,request_key="request",outcome="refund",now=refunded)
            finish(db,self.account,request_key="request",outcome="refund",now=refunded)
            self.assertEqual(balance(db,self.account,now=refunded),dict(subscription=3,purchased=10,reserved=0,available=13))
            expire(db,self.account,now=refunded+timedelta(days=7))
            expire(db,self.account,now=refunded+timedelta(days=7))
            self.assertEqual(balance(db,self.account,now=refunded+timedelta(days=7))["available"],10)
            self.assertEqual(db.scalar(select(func.count()).select_from(CreditWalletEvent).where(CreditWalletEvent.kind=="refund")),1)
            self.assertEqual(db.scalar(select(func.count()).select_from(CreditWalletEvent).where(CreditWalletEvent.kind=="expire")),1)

    def test_refund_before_expiry_keeps_original_expiry(self):
        with self.factory.begin() as db:
            self.seed(db);reserve(db,self.account,5,request_key="request",now=self.now)
            finish(db,self.account,request_key="request",outcome="refund",now=self.now)
            self.assertEqual(db.scalar(select(func.count()).select_from(CreditLot)),2)
            self.assertEqual(balance(db,self.account,now=self.now+timedelta(days=1))["available"],10)

    def test_grant_and_hold_replay_and_cross_account_access(self):
        with self.factory.begin() as db:
            self.seed(db)
            grant(db,self.account,10,source="purchased",operation_key="purchase",now=self.now)
            a=reserve(db,self.account,5,request_key="request",now=self.now)
            b=reserve(db,self.account,5,request_key="request",now=self.now)
            self.assertEqual(a.id,b.id)
            with self.assertRaises(WalletError):finish(db,self.other,request_key="request",outcome="refund",now=self.now)
            with self.assertRaises(WalletError):grant(db,self.account,11,source="purchased",operation_key="purchase",now=self.now)

    def test_insufficient_credit_and_invalid_source_do_not_mutate(self):
        with self.factory.begin() as db:
            self.seed(db)
            with self.assertRaises(WalletError):reserve(db,self.account,14,request_key="request",now=self.now)
            with self.assertRaises(WalletError):grant(db,self.account,5,source="purchased",operation_key="bad",now=self.now,expires_at=self.now+timedelta(days=1))
            self.assertEqual(balance(db,self.account,now=self.now)["available"],13)

    def test_expiry_does_not_destroy_held_credit_and_other_outcome_is_rejected(self):
        with self.factory.begin() as db:
            self.seed(db);reserve(db,self.account,2,request_key="request",now=self.now)
            later=self.now+timedelta(days=2);expire(db,self.account,now=later)
            self.assertEqual(balance(db,self.account,now=later),dict(subscription=0,purchased=10,reserved=2,available=10))
            finish(db,self.account,request_key="request",outcome="refund",now=later)
            with self.assertRaises(WalletError):finish(db,self.account,request_key="request",outcome="charge",now=later)

    def test_whole_transaction_rolls_back_lots_hold_and_ledger(self):
        with self.assertRaises(RuntimeError):
            with self.factory.begin() as db:
                self.seed(db);reserve(db,self.account,5,request_key="request",now=self.now)
                raise RuntimeError("Simulated rollback")
        with self.factory() as db:
            self.assertEqual(db.scalar(select(func.count()).select_from(CreditLot)),0)
            self.assertEqual(db.scalar(select(func.count()).select_from(CreditWalletEvent)),0)


if __name__=="__main__":unittest.main()
