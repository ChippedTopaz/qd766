import hashlib
import json
import os
import tempfile
import unittest
from datetime import date, datetime, timezone
from pathlib import Path
from unittest.mock import patch
from qd766.backend import recapture_log as logs
import test_trial_admin


class RecaptureLogTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=Path.cwd(), prefix='.tmp-recapture-log-test-')
        self.root = Path(self.temp.name)
        self.now = datetime(2026, 10, 16, 1, tzinfo=timezone.utc)
        self.patch = patch.object(logs, 'RECAPTURE_ROOT', self.root)
        self.patch.start()
        self.f = test_trial_admin.TrialAdminTests()
        self.f.setUp()
        for i in range(1, 13):
            self.fixture(date(2026, 10, i))

    def tearDown(self):
        self.f.tearDown()
        self.patch.stop()
        logs.read_checkpoint.cache_clear()
        self.temp.cleanup()

    def fixture(self, day, state='RUNNING', complete=False):
        directory = self.root / day.strftime('%Y%m%d')
        directory.mkdir(exist_ok=True)
        blocks = {f'month-2026-1:unit-{i}': {'state': 'SUCCESS', 'name': f'Tỉnh {i}', 'scoreChanges': 2}
                  for i in range(34 if complete else 12)}
        blocks['month-2026-1:national'] = {'state': 'SUCCESS', 'name': 'Cả nước'}
        path = directory / 'checkpoint.json'
        path.write_text(json.dumps({'state': state, 'provinceBlocks': 34, 'nationalBlocks': 1,
            'periods': [['month', 2026, 1]], 'startedAt': str(self.now), 'blocks': blocks,
            'backup': 'SECRET_PATH', 'backupSha256': 'SECRET_HASH'}), encoding='utf-8')
        os.utime(path, (self.now.timestamp(), self.now.timestamp()))
        return path

    def test_read_only_pages_and_scope(self):
        path = self.root / '20261012/checkpoint.json'
        before = hashlib.sha256(path.read_bytes()).hexdigest()
        first = logs.recapture_page(1, now=self.now)
        self.assertEqual(first['total'], 12)
        self.assertEqual(len(first['items']), 10)
        self.assertEqual(len(logs.recapture_page(2, now=self.now)['items']), 2)
        row = first['items'][0]
        self.assertEqual((row['completed'], row['expected']), (13, 35))
        self.assertEqual(row['publicationState'], 'not-published')
        self.assertNotIn('SECRET', json.dumps(first))
        self.assertNotIn('blocks', row)
        detail = logs.recapture_detail(date(2026, 10, 12), 1)
        self.assertEqual((detail['total'], len(detail['items'])), (13, 10))
        self.assertEqual(logs.recapture_detail(date(2026, 10, 12), 2)['total'], 13)
        self.assertEqual(logs.recapture_detail(date(2026, 10, 12), 1, 'issues')['total'], 0)
        self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), before)
        self.assertEqual(logs.recapture_page(1, date(2026, 10, 11), date(2026, 10, 12), now=self.now)['total'], 2)

    def test_complete_stale_corruption_and_unsafe_path(self):
        self.fixture(date(2026, 10, 13), 'AWAITING_ADMIN_REVIEW', complete=True)
        self.assertEqual(logs.recapture_record(date(2026, 10, 13), now=self.now)['state'], 'AWAITING_ADMIN_REVIEW')
        self.fixture(date(2026, 10, 14), 'AWAITING_ADMIN_REVIEW')
        self.assertEqual(logs.recapture_record(date(2026, 10, 14), now=self.now)['state'], 'INCOMPLETE')
        path = self.fixture(date(2026, 10, 15))
        os.utime(path, (self.now.timestamp() - 1500, self.now.timestamp() - 1500))
        self.assertEqual(logs.recapture_record(date(2026, 10, 15), now=self.now)['state'], 'NEEDS_CHECK')
        path.write_text('bad', encoding='utf-8')
        self.assertEqual(logs.recapture_record(date(2026, 10, 15), now=self.now)['state'], 'UNREADABLE')
        with patch.object(Path, 'is_symlink', return_value=True):
            self.assertEqual(logs.recapture_record(date(2026, 10, 13), now=self.now)['state'], 'UNREADABLE')

    def test_admin_routes_no_writes(self):
        route = '/api/v1/admin/logs/recaptures'
        r = self.f.client.get(route)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(self.f.client.get(route + '/2026-10-12?page=2').status_code, 200)
        self.assertEqual(self.f.client.get(route + '?page=0').status_code, 422)
        self.assertEqual(self.f.client.get(route + '?fromDate=2026-10-15&toDate=2026-10-01').status_code, 422)
        self.assertEqual(self.f.client.get(route + '/2026-10-12?state=bad').status_code, 422)
        from fastapi.testclient import TestClient
        anonymous = TestClient(self.f.app)
        self.assertEqual(anonymous.get(route).status_code, 401)
        self.assertEqual(anonymous.post(route).status_code, 401)
        self.assertEqual(self.f.client.post(route,headers=self.f.headers).status_code, 405)
        from qd766.backend.models import UserAccount
        with self.f.app.state.session_factory.begin() as db:
            db.get(UserAccount,self.f.admin_id).role='user'
        self.assertEqual(self.f.client.get(route).status_code,403)
