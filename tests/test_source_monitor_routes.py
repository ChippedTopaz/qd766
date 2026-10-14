import unittest
import uuid
from datetime import datetime, timezone
from sqlalchemy import select, func
from qd766.backend.models import SourceMonitorAlert, SourceMonitorRun, AdminAudit, UserAccount, Base
from qd766.backend.source_monitor import alert
import test_trial_admin


class SourceMonitorApiTests(unittest.TestCase):
    def setUp(self):
        self.fixture = test_trial_admin.TrialAdminTests(); self.fixture.setUp()
        self.client = self.fixture.client; self.factory = self.fixture.app.state.session_factory
        self.headers = self.fixture.headers
        with self.factory.begin() as db:
            for i in range(23): alert(db, 'structure', f'Thay đổi {i}', [i], {'changeCount': 1, 'changes': [{'field': 'maxScore', 'before': 6, 'after': 8}]})
            db.add(SourceMonitorRun(day=datetime.now(timezone.utc).date(), state='incomplete', details={'expected': 9, 'completed': []}, updated_at=datetime.now(timezone.utc)))
        self.url = '/api/v1/admin/source-monitor'

    def tearDown(self): self.fixture.tearDown()

    def test_pagination_filters_and_detail_with_advisory_only(self):
        result = self.client.get(self.url); self.assertEqual(result.status_code, 200, result.text)
        report = result.json(); self.assertEqual(report['total'], 23); self.assertEqual(report['unread'], 23)
        self.assertEqual(len(report['items']), 20); self.assertEqual(len(report['runs']), 1)
        self.assertEqual(len(self.client.get(self.url + '?page=2').json()['items']), 3)
        detail = self.client.get(self.url + '/' + report['items'][0]['id']).json()
        self.assertEqual(detail['recrawlPlan']['execution'], 'requires-admin-review')
        self.assertIn('changes', detail['details']); self.assertNotIn('details', report['items'][0])

    def test_review_csrf_audit_and_no_collection_credit_formula_mutation(self):
        item = self.client.get(self.url).json()['items'][0]; url = self.url + '/' + item['id'] + '/review'
        self.assertEqual(self.client.post(url, json={'action': 'read'}).status_code, 403)
        self.assertEqual(self.client.post(url, json={'action': 'resolve', 'note': '  '}, headers=self.headers).status_code, 422)
        result = self.client.post(url, json={'action': 'read'}, headers=self.headers)
        self.assertEqual(result.status_code, 200, result.text); self.assertFalse(result.json()['published'])
        self.assertEqual(self.client.get(self.url + '?state=unread').json()['total'], 22)
        result = self.client.post(url, json={'action': 'resolve', 'note': 'Đã kiểm tra, cần kế hoạch riêng'}, headers=self.headers)
        self.assertEqual(result.status_code, 200, result.text)
        self.assertEqual(self.client.get(self.url + '?state=resolved').json()['total'], 1)
        with self.factory() as db:
            self.assertEqual(db.scalar(select(func.count()).select_from(AdminAudit)), 2)
            for name in ('collection_jobs', 'credit_wallet_events', 'formula_config_revisions'):
                self.assertEqual(db.scalar(select(func.count()).select_from(Base.metadata.tables[name])), 0)

    def test_anonymous_and_non_admin_cannot_read_or_write_alerts(self):
        identifier = self.client.get(self.url).json()['items'][0]['id']
        with self.factory.begin() as db: db.get(UserAccount, self.fixture.admin_id).role = 'user'
        for path in (self.url, self.url + '/' + identifier): self.assertEqual(self.client.get(path).status_code, 403)
        self.assertEqual(self.client.post(self.url + '/' + identifier + '/review', json={'action': 'read'}, headers=self.headers).status_code, 403)
        self.client.cookies.clear()
        self.assertEqual(self.client.get(self.url).status_code, 401)

    def test_invalid_input_and_missing_schema_fail_explicitly(self):
        for query in ('?page=0', '?state=not-real'):
            self.assertEqual(self.client.get(self.url + query).status_code, 422)
        self.assertEqual(self.client.get(self.url + '/bad-id').status_code, 422)
        self.assertEqual(self.client.get(self.url + '/' + str(uuid.uuid4())).status_code, 404)
        Base.metadata.tables['source_monitor_samples'].drop(self.fixture.app.state.engine)
        self.assertEqual(self.client.get(self.url).status_code, 503)


if __name__ == '__main__': unittest.main()
