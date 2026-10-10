import importlib.util
import io
import sys
import time
import unittest
import uuid
from contextlib import redirect_stdout
from datetime import timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

from sqlalchemy import select, func
from qd766.backend.config import Settings
from qd766.backend.database import create_database_engine, create_session_factory
from qd766.backend.models import Base, CollectionJob, CollectionControl
from qd766.backend.jobs import (enqueue_job, acquire_collection_lease, claim_next_job,
    renew_worker_lease, WorkerLeaseLost, utc_now)
from qd766.backend.worker import run_one_job
from qd766.collection import CollectionError


class WorkerResilienceTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_database_engine(Settings(database_url='sqlite://'))
        Base.metadata.create_all(self.engine)
        self.factory = create_session_factory(self.engine)
        self.addCleanup(self.engine.dispose)

    def enqueue(self, payload):
        with self.factory.begin() as db:
            return enqueue_job(db, payload)[0].id

    def test_long_job_renews_both_leases_and_blocks_another_worker(self):
        job_id = self.enqueue({'test':'long'})
        start = utc_now()
        with self.factory.begin() as db:
            acquire_collection_lease(db, 'first', lease_seconds=1800, now=start)
            claim_next_job(db, 'first', now=start)
        with self.factory.begin() as db:
            renew_worker_lease(db, 'first', now=start+timedelta(minutes=29))
        with self.factory.begin() as db:
            self.assertEqual(acquire_collection_lease(db, 'second', lease_seconds=1800,
                now=start+timedelta(minutes=31)), 'busy')
            self.assertEqual(db.get(CollectionJob, job_id).locked_at.minute,
                (start+timedelta(minutes=29)).minute)
            with self.assertRaises(WorkerLeaseLost):
                renew_worker_lease(db, 'second')

    def test_stale_worker_cannot_import_or_settle(self):
        job_id = self.enqueue({'test':'stale'})
        def processor(*args):
            with self.factory.begin() as db:
                db.get(CollectionControl, 'dvcqg').lease_locked_by = 'replacement'
                db.get(CollectionJob, job_id).locked_by = 'replacement'
            return {}
        with patch('qd766.backend.worker.store_normalized_snapshot') as store, \
             patch('qd766.backend.worker.settle_paid_requests_for_job') as settle:
            result = run_one_job(self.factory, processor, worker_id='old')
        self.assertEqual(result.state, 'lease-lost')
        store.assert_not_called(); settle.assert_not_called()
        with self.factory() as db:
            self.assertEqual(db.get(CollectionJob, job_id).locked_by, 'replacement')

    def test_burst_1000_submissions_dedup_100_jobs_drain_once(self):
        started = time.monotonic()
        for number in range(100):
            ids = {self.enqueue({'test':'load', 'number':number}) for _ in range(10)}
            self.assertEqual(len(ids), 1)
        seen = set()
        def processor(job_id, payload):
            self.assertNotIn(job_id, seen)
            seen.add(job_id)
            return {}
        with patch('qd766.backend.worker.store_normalized_snapshot', return_value=object()):
            for _ in range(100):
                self.assertEqual(run_one_job(self.factory, processor, worker_id='load').state, 'succeeded')
            self.assertIsNone(run_one_job(self.factory, processor, worker_id='load'))
        self.assertEqual(len(seen), 100)
        with self.factory() as db:
            self.assertEqual(db.scalar(select(func.count()).select_from(CollectionJob)
                .where(CollectionJob.state=='succeeded')), 100)
            self.assertIsNone(db.get(CollectionControl,'dvcqg').lease_locked_by)
        print(f'QUEUE_LOAD_SIMULATED: submissions=1000 unique_jobs=100 processed_once=100 seconds={time.monotonic()-started:.2f}')

    def test_collection_failures_retry_then_fail_without_stopping_next_job(self):
        bad = self.enqueue({'test':'bad'})
        self.enqueue({'test':'good'})
        def processor(job_id, payload):
            if job_id == bad:
                raise CollectionError('simulated transient source failure')
            return {}
        with patch('qd766.backend.worker.store_normalized_snapshot', return_value=object()):
            states = [run_one_job(self.factory, processor, worker_id='retry',
                retry_delay_seconds=0).state for _ in range(4)]
        # SQLite timestamps can tie; FIFO then UUID is still deterministic.
        self.assertCountEqual(states, ['queued','queued','failed','succeeded'])
        with self.factory() as db:
            self.assertEqual(db.get(CollectionJob,bad).attempts,3)

    def test_database_outage_loop_recovers_and_does_not_log_sensitive_parameters(self):
        from sqlalchemy.exc import OperationalError
        path = Path(__file__).resolve().parents[1]/'tools/run_collection_worker.py'
        spec = importlib.util.spec_from_file_location('worker_runner_test', path)
        runner = importlib.util.module_from_spec(spec); spec.loader.exec_module(runner)
        output = io.StringIO()
        failure = OperationalError('secret SQL', {'password':'secret'}, Exception('secret URL'))
        with patch.object(sys,'argv',['worker']), patch.object(runner,'load_environment_file'), \
             patch.object(runner,'create_database_engine', return_value=MagicMock()), \
             patch.object(runner,'create_session_factory',return_value=MagicMock()), \
             patch.object(runner,'run_one_job',side_effect=[failure,None,KeyboardInterrupt]), \
             patch.object(runner.time,'sleep') as sleep, redirect_stdout(output):
            self.assertEqual(runner.main(),0)
        self.assertEqual(sleep.call_args_list[0].args,(5,))
        self.assertIn('worker-database-retry',output.getvalue())
        self.assertNotIn('secret',output.getvalue())


if __name__ == '__main__':
    unittest.main()
