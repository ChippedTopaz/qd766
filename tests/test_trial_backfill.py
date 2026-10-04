import sys
import unittest
import uuid
from pathlib import Path
from datetime import datetime,timedelta,timezone
from sqlalchemy import create_engine, select, func
from sqlalchemy.orm import sessionmaker

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"src"))
from qd766.backend.models import Base,UserAccount,Department,TrialInvitation,CreditWalletEvent,SubscriptionCycle
from qd766.backend.trial_backfill import review,apply_selected
from qd766.backend.credit_wallet import WalletError,balance


class TrialBackfillTests(unittest.TestCase):
    def setUp(self):
        self.engine=create_engine("sqlite+pysqlite://")
        Base.metadata.create_all(self.engine)
        self.factory=sessionmaker(self.engine,expire_on_commit=False,
            info={"real_wallet_enabled":True,"source_wallet_enabled":True})
        self.now=datetime(2026,10,4,tzinfo=timezone.utc)
        self.admin_id=uuid.uuid4();self.account_id=uuid.uuid4();self.operation=uuid.uuid4()
        with self.factory.begin() as db:
            root=Department(id=uuid.uuid4(),name="Test",attributes={});db.add(root);db.flush()
            db.add_all([UserAccount(id=self.admin_id,external_subject="google:owner",email="vietnt89@gmail.com",
                display_name="Owner",role="admin",active=True,trial_admitted=True,root_department_id=root.id),
                UserAccount(id=self.account_id,external_subject="google:old",display_name="Old",active=True,
                    trial_admitted=True,root_department_id=root.id)])
            db.flush()
            db.add(TrialInvitation(token_hash=uuid.uuid4().hex,created_by=self.admin_id,
                root_department_id=root.id,access_tier="province",expires_at=self.now-timedelta(days=1),
                used_at=self.now-timedelta(days=2),used_by=self.account_id))

    def tearDown(self):self.engine.dispose()

    def apply(self,db,**kwargs):
        return apply_selected(db,account_ids=kwargs.pop("account_ids",[self.account_id]),
            administrator_id=self.admin_id,operation_id=self.operation,now=self.now,**kwargs)

    def test_review_is_read_only_and_apply_is_idempotent(self):
        with self.factory.begin() as db:
            report,_=review(db,db.get(UserAccount,self.account_id))
            self.assertTrue(report["eligible"])
            self.assertEqual(db.scalar(select(func.count()).select_from(CreditWalletEvent)),0)
            self.assertEqual(self.apply(db),dict(activated=1,replayed=False))
            self.assertEqual(self.apply(db),dict(activated=0,replayed=True))
            self.assertEqual(balance(db,self.account_id,now=self.now)["available"],100)
            self.assertEqual(db.get(UserAccount,self.account_id).credit_balance,0)
            cycle=db.scalar(select(SubscriptionCycle).where(SubscriptionCycle.account_id==self.account_id))
            self.assertEqual(cycle.starts_at.replace(tzinfo=timezone.utc),self.now)
            self.assertEqual(review(db,db.get(UserAccount,self.account_id))[0]["reason"],"subscription_already_exists")

    def test_locked_admin_positive_legacy_and_invalid_invitation_rejected(self):
        with self.factory.begin() as db:
            self.assertEqual(review(db,db.get(UserAccount,self.admin_id))[0]["reason"],"admin_excluded")
            account=db.get(UserAccount,self.account_id)
            account.active=False;db.flush()
            self.assertEqual(review(db,account)[0]["reason"],"locked")
            with self.assertRaises(WalletError):self.apply(db)
            account.active=True;account.credit_balance=30;db.flush()
            self.assertEqual(review(db,account)[0]["reason"],"legacy_balance_review_required")
            account.credit_balance=0
            invitation=db.scalar(select(TrialInvitation));invitation.revoked_at=self.now;db.flush()
            with self.assertRaises(WalletError):self.apply(db)
            self.assertEqual(db.scalar(select(func.count()).select_from(CreditWalletEvent)),0)

    def test_disabled_mode_wrong_owner_and_changed_replay_rejected(self):
        with self.factory.begin() as db:
            db.info["real_wallet_enabled"]=False
            with self.assertRaises(WalletError):self.apply(db)
            db.info["real_wallet_enabled"]=True
            owner=db.get(UserAccount,self.admin_id);owner.email="other@example.test";db.flush()
            with self.assertRaises(WalletError):self.apply(db)
            owner.email="vietnt89@gmail.com";db.flush()
            self.apply(db)
            with self.assertRaises(WalletError):self.apply(db,account_ids=[self.admin_id])

    def test_selected_batch_rolls_back_on_ineligible_account(self):
        with self.assertRaises(WalletError):
            with self.factory.begin() as db:
                self.apply(db,account_ids=[self.account_id,self.admin_id])
        with self.factory() as db:
            self.assertEqual(db.scalar(select(func.count()).select_from(CreditWalletEvent)),0)
            self.assertEqual(db.scalar(select(func.count()).select_from(SubscriptionCycle)),0)


if __name__=="__main__":unittest.main()
