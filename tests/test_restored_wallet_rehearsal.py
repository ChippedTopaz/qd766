import sys
import unittest
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from rehearse_restored_wallet import scenarios
from qd766.backend.models import Base


class RestoredWalletRehearsalTests(unittest.TestCase):
    def test_scenarios_and_rollback(self):
        engine = create_engine("sqlite+pysqlite://")
        try:
            Base.metadata.create_all(engine)
            with engine.connect() as connection:
                transaction = connection.begin()
                try:
                    with Session(bind=connection, info={"source_wallet_enabled": True}) as db:
                        self.assertEqual(len(scenarios(db)), 8)
                finally:
                    if transaction.is_active:
                        transaction.rollback()
            with Session(engine) as db:
                from sqlalchemy import select, func
                from qd766.backend.models import UserAccount, CreditWalletEvent
                self.assertEqual(db.scalar(select(func.count()).select_from(UserAccount)), 0)
                self.assertEqual(db.scalar(select(func.count()).select_from(CreditWalletEvent)), 0)
        finally:
            engine.dispose()


if __name__ == "__main__":
    unittest.main()
