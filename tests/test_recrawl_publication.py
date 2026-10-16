import unittest
from sqlalchemy import create_engine,select,func,event
from sqlalchemy.orm import Session
from qd766.backend.models import Base,Snapshot,UserAccount
from qd766.backend.importer import store_normalized_snapshot
from publish_historical_recrawl import publication_sql_guard
from test_backend import snapshot_payload


class PublicationTests(unittest.TestCase):
    def test_write_scope(self):
        for sql in ['SELECT 1','SAVEPOINT sa_savepoint_1','RELEASE SAVEPOINT sa_savepoint_1',
            'INSERT INTO snapshots (id) VALUES (1)','UPDATE snapshots SET created_at=1',
            'DELETE FROM daily_observations WHERE daily_observations.id IN (1)']:
            publication_sql_guard(None,None,sql,None,None,False)
        for sql in ['DELETE FROM snapshots','DELETE FROM daily_observations','UPDATE user_accounts SET credit_balance=0',
            'INSERT INTO credit_ledger_entries (id) VALUES (1)','UPDATE formula_config_head SET id=0']:
            with self.assertRaises(RuntimeError):publication_sql_guard(None,None,sql,None,None,False)

    def test_rollback_and_append_preserve_old_snapshot(self):
        engine=create_engine('sqlite://');Base.metadata.create_all(engine)
        with Session(engine) as db,db.begin():
            old=store_normalized_snapshot(db,snapshot_payload(),observation_id='original');old_id=old.id
        event.listen(engine,'before_cursor_execute',publication_sql_guard)
        with self.assertRaisesRegex(RuntimeError,'simulate-validation-failure'):
            with Session(engine) as db,db.begin():
                store_normalized_snapshot(db,snapshot_payload(),observation_id='approved-replacement')
                raise RuntimeError('simulate-validation-failure')
        with Session(engine) as db:
            self.assertEqual(db.scalar(select(func.count()).select_from(Snapshot)),1)
            self.assertIsNotNone(db.get(Snapshot,old_id))
        with Session(engine) as db,db.begin():
            new=store_normalized_snapshot(db,snapshot_payload(),observation_id='approved-replacement')
            self.assertNotEqual(new.id,old_id)
        with Session(engine) as db:
            self.assertEqual(db.scalar(select(func.count()).select_from(Snapshot)),2)
            self.assertIsNotNone(db.get(Snapshot,old_id))
            self.assertEqual(db.scalar(select(func.count()).select_from(UserAccount)),0)
        engine.dispose()
