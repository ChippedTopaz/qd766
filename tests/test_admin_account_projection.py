import sys
import unittest
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from qd766.backend.models import Base, UserAccount, CreditWalletEnrollment, CreditLot, SubscriptionCycle, AccountCollectionPermission
from qd766.backend.admin_accounts import account_projections
from qd766.backend.wallet_access import credits, subscription_summary
from qd766.backend.collection_permissions import can_collect


class AdminProjectionTests(unittest.TestCase):
    def test_bounded_queries_and_parity_with_wallet_rules(self):
        engine = create_engine("sqlite+pysqlite://")
        Base.metadata.create_all(engine)
        now = datetime.now(timezone.utc)
        try:
            with Session(engine, info={"source_wallet_enabled": True}) as db:
                users = []
                for index in range(80):
                    user = UserAccount(external_subject=f"projection:{index}", display_name="Test",
                        active=index % 7 != 0, trial_admitted=True, access_tier="agency",
                        root_department_id=uuid.uuid4(), unit_department_id=uuid.uuid4(), credit_balance=31, credit_reserved=2)
                    db.add(user); db.flush(); users.append(user)
                    db.add(AccountCollectionPermission(account_id=user.id, enabled=index % 2 == 0))
                    if index % 5 == 0:
                        continue  # Legacy wallets must not be reclassified.
                    db.add(CreditWalletEnrollment(account_id=user.id, created_at=now))
                    for source, amount, reserved, expires in [
                        ("subscription", 70, 3, now + timedelta(days=3)),
                        ("subscription", 50, 4, now - timedelta(days=1)),
                        ("purchased", 120, 1, None)]:
                        db.add(CreditLot(account_id=user.id, source=source, available=amount,
                            reserved=reserved, expires_at=expires, created_at=now))
                    if index % 4 == 0:
                        continue  # An enrolled wallet can have no subscription yet.
                    for offset in (-40, -5, 25):
                        db.add(SubscriptionCycle(account_id=user.id, operation_key=f"cycle:{offset}",
                            tier="agency", origin="paid", starts_at=now + timedelta(days=offset),
                            ends_at=now + timedelta(days=offset + 30), included_credit=100))
                db.flush()
                queries = []
                def capture(connection, cursor, statement, parameters, context, many):
                    queries.append(statement)
                event.listen(engine, "before_cursor_execute", capture)
                actual = account_projections(db, users, now=now)
                event.remove(engine, "before_cursor_execute", capture)
                self.assertEqual(len(queries), 4, "Query count must not grow per account")
                self.assertTrue(all(q.lstrip().upper().startswith("SELECT") for q in queries))
                for user in users:
                    row = actual[user.id]
                    self.assertEqual((row["credits"], row["reservedCredits"]), credits(db, user, now=now))
                    self.assertEqual(row["subscription"], subscription_summary(db, user, now=now))
                    self.assertEqual(row["canCollect"], can_collect(db, user.id))
                db.info["default_collection_access"] = True
                actual = account_projections(db, users, now=now)
                for user in users:
                    self.assertEqual(actual[user.id]["canCollect"], can_collect(db, user.id))
                db.info["source_wallet_enabled"] = False
                actual = account_projections(db, users, now=now)
                for user in users:
                    self.assertEqual(actual[user.id]["credits"], 31)
                    self.assertIsNone(actual[user.id]["subscription"])
                    self.assertFalse(actual[user.id]["canActivateTrial"])
        finally:
            engine.dispose()
