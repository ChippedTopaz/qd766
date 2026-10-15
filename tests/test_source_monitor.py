import copy
import hashlib
import importlib.util
import json
import sqlite3
import sys
import tempfile
import unittest
import uuid
from contextlib import closing
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
sys.path.insert(0, str(ROOT / 'tools'))
from sqlalchemy import func, inspect, select
from alembic.migration import MigrationContext
from alembic.operations import Operations
from qd766.backend.config import Settings
from qd766.backend.database import create_database_engine, create_session_factory
from qd766.backend.models import (
    Base, NationalSummarySnapshot, SourceMonitorAlert, SourceMonitorSample,
    SourceMonitorRun, SourceMonitorBaseline, CollectionControl,
)
from qd766.backend.national_summaries import store_national_summary
from qd766.backend.source_monitor import (
    ready, scalar, structure_profile, national_profile, observe_profile,
    capture_profiles, score_profile, closed_month_baselines, record_month_sample,
)
from qd766.collection import CollectionError, SafetyStop, TransportResponse
from qd766.national_summary import NationalSummaryCapture, collect_national_summary
from qd766.periods import PeriodSelection
from test_national_summary import response_body, FakeTransport
import run_source_monitor as runner

NOW = datetime(2026, 10, 13, 23, 0, tzinfo=timezone.utc)  # 14/10 06:00 Vietnam


def metric_data():
    root = {'departmentId': str(uuid.uuid4()), 'totalMaxScore': 18, 'totalScore': 10,
            'metrics': [{'code': 'A', 'name': 'Chỉ tiêu A', 'maxScore': 6,
                         'numerator': 1, 'denominator': 2, 'ratio': 50, 'score': 3},
                        {'code': 'B', 'name': 'Chỉ tiêu B', 'maxScore': 12}]}
    return {'overview': root, 'evaluation': []}


def capture(month=9, data=None, at=NOW):
    data = data or response_body()['data']
    return NationalSummaryCapture(PeriodSelection('month', 2026, month), {}, data,
                                  hashlib.sha256(json.dumps(data).encode()).hexdigest(), at)


class MonitorDatabaseFixture:
    def setUp(self):
        self.engine = create_database_engine(Settings(database_url='sqlite+pysqlite://'))
        Base.metadata.create_all(self.engine)
        self.factory = create_session_factory(self.engine)

    def tearDown(self):
        self.engine.dispose()

    def baseline(self, month=9, at=NOW - timedelta(days=1)):
        with self.factory.begin() as db:
            row, _ = store_national_summary(db, capture(month, at=at))
            return row.id


class MonitorDatabaseTests(MonitorDatabaseFixture, unittest.TestCase):

    def test_ready_requires_every_table_not_only_first_and_last(self):
        with self.factory() as db:
            self.assertTrue(ready(db))
        Base.metadata.tables['source_monitor_samples'].drop(self.engine)
        with self.factory() as db:
            self.assertFalse(ready(db))

    def test_decimal_format_semantic_equality_no_scientific_notation(self):
        self.assertEqual(scalar(20), '20'); self.assertEqual(scalar(20.0), '20')
        self.assertEqual(scalar(-0.0), scalar(0)); self.assertEqual(scalar(100), '100')

    def test_normal_numeric_changes_order_and_unit_names_are_not_structure(self):
        data = metric_data(); changed = copy.deepcopy(data)
        changed['overview'].update(totalScore=999, departmentName='Đổi tên', totalMaxScore=18.0)
        changed['overview']['metrics'].reverse()
        changed['overview']['metrics'][1].update(numerator=500, denominator=800, score=4)
        self.assertEqual(structure_profile(data), structure_profile(changed))

    def test_max_score_metric_add_remove_and_declared_threshold_are_detected(self):
        before = structure_profile(metric_data())
        for change in ('maximum', 'add', 'remove', 'threshold', 'name'):
            data = metric_data(); root = data['overview']
            if change == 'maximum': root['metrics'][0]['maxScore'] = 7
            if change == 'add': root['metrics'].append({'code': 'C', 'maxScore': 1})
            if change == 'remove': root['metrics'].pop()
            if change == 'threshold': root['metrics'][0]['threshold'] = 80
            if change == 'name': root['metrics'][0]['name'] = 'Tên mới'
            with self.subTest(change=change), self.factory.begin() as db:
                item = observe_profile(db, change, structure_profile(data),
                    {'rootId': 'one', 'periodType': 'month', 'group': 'MDHL'}, seed=before)
                self.assertTrue(item.details['changeCount'])
                self.assertFalse(item.details['confirmed'])

    def test_inventory_churn_alone_does_not_report_removed_metric_cohort(self):
        data = metric_data(); child = copy.deepcopy(data['overview'])
        child['departmentType'] = 'COMMUNE'; data['evaluation'] = [child]
        changed = copy.deepcopy(data); changed['evaluation'] = []
        with self.factory.begin() as db:
            self.assertIsNone(observe_profile(db, 'inventory', structure_profile(changed),
                {'rootId': 'one', 'periodType': 'month', 'group': 'MDHL'}, seed=structure_profile(data)))

    def test_alert_dedupes_system_wide_change_and_reopens_after_review(self):
        before = structure_profile(metric_data()); data = metric_data()
        data['overview']['metrics'][0]['maxScore'] = 8; after = structure_profile(data)
        with self.factory.begin() as db:
            first = observe_profile(db, 'root-one', after,
                {'rootId': 'one', 'periodType': 'year', 'group': 'MDHL'}, seed=before)
            db.flush(); first.resolved_at = NOW; first.read_at = NOW
            second = observe_profile(db, 'root-two', after,
                {'rootId': 'two', 'periodType': 'year', 'group': 'MDHL'}, seed=before)
            self.assertEqual(first.id, second.id); self.assertEqual(second.occurrences, 2)
            self.assertTrue(second.details['confirmed']); self.assertIsNone(second.resolved_at)
            self.assertIsNone(second.read_at)
            self.assertIsNone(observe_profile(db, 'root-two', after,
                {'rootId': 'two', 'periodType': 'year', 'group': 'MDHL'}))

    def test_capture_hash_and_path_escape_are_rejected(self):
        with tempfile.TemporaryDirectory(dir=ROOT, prefix='.tmp-source-monitor-test-') as folder:
            root = Path(folder); raw = json.dumps({'code': 'OK', 'data': metric_data()}).encode()
            (root / 'group.json').write_bytes(raw)
            manifest = {'captures': [{'group': 'test', 'file': 'group.json', 'sha256': hashlib.sha256(raw).hexdigest()}]}
            self.assertIn('test', capture_profiles(root, manifest))
            manifest['captures'][0]['sha256'] = '0' * 64
            with self.assertRaises(ValueError): capture_profiles(root, manifest)
            manifest['captures'][0]['file'] = '../outside.json'
            with self.assertRaises(ValueError): capture_profiles(root, manifest)

    def test_closed_months_only_latest_complete_and_vietnam_boundary(self):
        september = self.baseline(9); self.baseline(10); self.baseline(11)
        with self.factory.begin() as db:
            data = copy.deepcopy(response_body()['data']); data['evaluation'][0]['totalScore'] += 1
            newer = capture(9, data=data, at=NOW)
            new, _ = store_national_summary(db, newer)
            result = closed_month_baselines(db, NOW)
            self.assertEqual([r.id for r in result], [new.id]); self.assertNotEqual(new.id, september)
            # UTC still 30/09 but Vietnam is 01/10; September is closed.
            boundary = datetime(2026, 9, 30, 18, 0, tzinfo=timezone.utc)
            self.assertEqual(len(closed_month_baselines(db, boundary)), 1)

    def test_sample_is_separate_confirmed_next_day_and_does_not_publish(self):
        identifier = self.baseline(); changed = copy.deepcopy(response_body()['data'])
        changed['evaluation'][0]['totalScore'] += .1
        for offset, confirmed in ((0, False), (1, True)):
            with self.factory.begin() as db:
                row = db.get(NationalSummarySnapshot, identifier)
                self.assertEqual(record_month_sample(db, row, capture(data=changed), now=NOW + timedelta(days=offset)), 1)
                db.flush()
                item = db.scalar(select(SourceMonitorAlert).order_by(SourceMonitorAlert.created_at.desc()))
                self.assertEqual(item.details['confirmed'], confirmed)
                self.assertEqual(db.scalar(select(func.count()).select_from(SourceMonitorAlert)),offset+1)
                self.assertEqual(db.scalar(select(func.count()).select_from(SourceMonitorSample)), 1)
                self.assertEqual(db.scalar(select(func.count()).select_from(NationalSummarySnapshot)), 1)
                self.assertEqual(row.response_data['evaluation'][0]['totalScore'], 61.86)

    def test_unchanged_semantic_numbers_do_not_create_alert(self):
        identifier = self.baseline(); changed = copy.deepcopy(response_body()['data'])
        changed['evaluation'][1]['totalScore'] = 60
        with self.factory.begin() as db:
            self.assertEqual(record_month_sample(db, db.get(NationalSummarySnapshot, identifier), capture(data=changed)), 0)
            self.assertEqual(db.scalar(select(func.count()).select_from(SourceMonitorAlert)), 0)

    def test_inventory_period_and_invalid_scores_are_not_successful_samples(self):
        identifier = self.baseline()
        with self.factory.begin() as db:
            baseline = db.get(NationalSummarySnapshot, identifier)
            with self.assertRaises(ValueError): record_month_sample(db, baseline, capture(8))
            data = copy.deepcopy(response_body()['data']); data['evaluation'].pop()
            with self.assertRaises(ValueError): record_month_sample(db, baseline, capture(data=data))
            for invalid in (True, None, '61', float('nan'), float('inf')):
                data = copy.deepcopy(response_body()['data']); data['evaluation'][0]['totalScore'] = invalid
                with self.subTest(value=invalid), self.assertRaises(ValueError): score_profile(data)
            self.assertEqual(db.scalar(select(func.count()).select_from(SourceMonitorSample)), 0)

    def test_national_hook_reports_added_group_before_parser_rejects(self):
        body = response_body(); body['data']['evaluation'][0]['groupScores']['NEW'] = 3
        transport = FakeTransport(TransportResponse(200, json.dumps(body).encode(), 'application/json'))
        seen = []
        with self.assertRaises(CollectionError):
            collect_national_summary(PeriodSelection('month', 2026, 9), transport,
                                    on_data=lambda data: seen.append(national_profile(data)))
        self.assertEqual(len(seen), 1); self.assertIn('NEW', seen[0]['root/groupCodes'][0])

    def test_additive_migration_creates_exact_model_tables(self):
        # Start from a model-based predecessor; apply only reviewed additive revision.
        for table in reversed(Base.metadata.sorted_tables):
            if table.name.startswith('source_monitor_'): table.drop(self.engine)
        spec = importlib.util.spec_from_file_location('source_revision', ROOT / 'alembic/versions/20261014_0028_source_monitor.py')
        module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
        with self.engine.begin() as connection:
            with Operations.context(MigrationContext.configure(connection)):
                module.upgrade()
        inspector = inspect(self.engine)
        for name, table in Base.metadata.tables.items():
            if name.startswith('source_monitor_'):
                self.assertEqual({c['name'] for c in inspector.get_columns(name)}, set(table.columns.keys()))
        with self.factory() as db: self.assertTrue(ready(db))


class MonitorRunnerTests(MonitorDatabaseFixture, unittest.TestCase):
    # Do not inherit the database feature tests a second time.
    def setUp(self):
        super().setUp(); self.temporary = tempfile.TemporaryDirectory(dir=ROOT, prefix='.tmp-source-monitor-test-'); self.root = Path(self.temporary.name)
        self.calls = []; self.created = []
        with self.factory.begin() as db: db.add(CollectionControl(key='dvcqg', circuit_state='closed'))
        self.baseline()

    def tearDown(self):
        self.temporary.cleanup(); super().tearDown()

    def checkpoint(self, state='COMPLETE', completed=102):
        folder = self.root / 'data/daily-collection/2026-10-13'; folder.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(folder / 'crawl_state.sqlite')) as db:
            db.execute('CREATE TABLE IF NOT EXISTS blocks (block_key TEXT, state TEXT, details TEXT)')
            db.execute('DELETE FROM blocks')
            db.execute('INSERT INTO blocks VALUES (?,?,?)', ('run-status', state, json.dumps({'completed': completed, 'expected': 102})))
            db.commit()

    def transport(self, **options):
        self.created.append(options)
        class Transport:
            def close(inner): self.calls.append('closed')
        return Transport()

    def read(self, period, transport, *, on_data):
        self.created[-1]['guard'](); self.calls.append(period)
        data = copy.deepcopy(response_body()['data']); on_data(data)
        return capture(period.value, data=data)

    def run_check(self, **options):
        return runner.execute(self.factory, root=self.root, now=NOW, transport_factory=self.transport,
                              read_capture=self.read, sleeper=lambda seconds: None, **options)

    def test_runner_complete_once_no_publication_or_credit_job_changes(self):
        self.checkpoint(); result = self.run_check(); self.assertEqual(result['state'], 'complete')
        self.assertEqual(self.calls, [PeriodSelection('month', 2026, 9), 'closed'])
        self.assertEqual(self.created[0]['max_workers'], 1); self.assertEqual(self.created[0]['spacing'], 1)
        self.run_check(); self.assertEqual(len(self.created), 1)
        with self.factory() as db:
            self.assertEqual(db.scalar(select(func.count()).select_from(NationalSummarySnapshot)), 1)
            for name in ('collection_jobs', 'credit_wallet_events', 'formula_config_revisions'):
                self.assertEqual(db.scalar(select(func.count()).select_from(Base.metadata.tables[name])), 0)
            self.assertIsNone(db.get(CollectionControl, 'dvcqg').lease_locked_by)

    def test_missing_incomplete_and_failed_morning_never_contact_source(self):
        for status, count in (('NOT_STARTED', 0), ('COMPLETE', 101), ('INCOMPLETE', 10), ('HALTED', 0)):
            if status != 'NOT_STARTED': self.checkpoint(status, count)
            result = self.run_check(); self.assertEqual(result['state'], 'not-checked')
        self.assertEqual(self.created, [])

    def test_before_six_guard(self):
        self.checkpoint()
        with self.assertRaises(ValueError):
            runner.execute(self.factory, root=self.root, now=NOW - timedelta(minutes=1), transport_factory=self.transport)
        self.assertEqual(self.created, [])

    def test_running_morning_waits_then_continues_without_early_source_call(self):
        def finish(_seconds):
            if _seconds == 30:
                self.assertEqual(self.created, []); self.checkpoint()
        self.checkpoint('RUNNING', 10)
        result = runner.execute(self.factory, root=self.root, now=NOW, sleeper=finish,
                                transport_factory=self.transport, read_capture=self.read)
        self.assertEqual(result['state'], 'complete')

    def test_running_morning_timeout_is_not_unchanged(self):
        self.checkpoint('RUNNING', 10)
        with patch.object(runner.time, 'monotonic', side_effect=[0, 20000]): result = self.run_check()
        self.assertEqual(result['state'], 'not-checked'); self.assertEqual(self.created, [])

    def test_source_pause_no_request_and_preserves_safety_state(self):
        self.checkpoint()
        with self.factory.begin() as db: db.get(CollectionControl, 'dvcqg').circuit_state = 'open'
        self.assertEqual(self.run_check()['state'], 'paused'); self.assertEqual(self.calls, ['closed'])
        with self.factory() as db: self.assertEqual(db.get(CollectionControl, 'dvcqg').circuit_state, 'open')

    def test_fresh_user_lease_not_stolen_and_busy_recorded(self):
        self.checkpoint()
        with self.factory.begin() as db:
            item = db.get(CollectionControl, 'dvcqg'); item.lease_locked_by = 'user-worker'
            item.lease_locked_at = datetime.now(timezone.utc)
        with patch.object(runner.time, 'monotonic', side_effect=[0, 0, 0, 0, 400]): result = self.run_check()
        self.assertEqual(result['state'], 'not-checked'); self.assertEqual(self.calls, ['closed'])
        with self.factory() as db: self.assertEqual(db.get(CollectionControl, 'dvcqg').lease_locked_by, 'user-worker')

    def test_capture_error_incomplete_alert_no_sample_and_can_retry(self):
        self.checkpoint()
        with patch.object(self, 'read', side_effect=CollectionError('mock failure')):
            self.assertEqual(self.run_check()['state'], 'incomplete')
        self.assertEqual(self.run_check()['state'], 'complete')
        with self.factory() as db: self.assertEqual(db.scalar(select(func.count()).select_from(SourceMonitorSample)), 1)

    def test_transport_start_error_still_recorded(self):
        self.checkpoint()
        with patch.object(self, 'transport', side_effect=RuntimeError('mock failure')):
            self.assertEqual(self.run_check()['state'], 'incomplete')
        with self.factory() as db: self.assertEqual(db.get(SourceMonitorRun, date(2026, 10, 14)).details['error'], 'RuntimeError')

    def test_remote_safety_stop_releases_own_lease_and_opens_existing_circuit(self):
        self.checkpoint()
        with patch.object(self, 'read', side_effect=SafetyStop('Mock source rejection')):
            self.assertEqual(self.run_check()['state'], 'paused')
        with self.factory() as db:
            control = db.get(CollectionControl, 'dvcqg')
            self.assertEqual(control.circuit_state, 'open'); self.assertIsNone(control.lease_locked_by)
            self.assertEqual(db.scalar(select(func.count()).select_from(SourceMonitorSample)), 0)

    def test_drift_saves_evidence_without_replacing_main_snapshot(self):
        self.checkpoint()
        def read(period, transport, *, on_data):
            data = copy.deepcopy(response_body()['data']); data['evaluation'][0]['totalScore'] += .1
            on_data(data); return capture(data=data)
        with patch.object(self, 'read', side_effect=read): self.assertEqual(self.run_check()['state'], 'complete')
        self.assertEqual(len(list((self.root / 'data/source-monitor/2026-10-14').glob('*.json'))), 1)


if __name__ == '__main__': unittest.main()
