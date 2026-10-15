import unittest, uuid
from sqlalchemy import select, event
from qd766.backend.models import DailyObservation, UserAccount
from test_daily_selection import SavedDaySelectionTests
from test_backend import ROOT_ID, CHILD_ID


class RankingHistoryTests(unittest.TestCase):
    def setUp(self):
        self.fixture=SavedDaySelectionTests();self.fixture.setUp()
        self.client=self.fixture.client;self.factory=self.fixture.factory
        with self.factory.begin() as db:
            for row in db.scalars(select(DailyObservation)):
                row.period_type='year';row.period_value=None
        self.params={'root_department_id':ROOT_ID,'unit_id':CHILD_ID,'year':2026}

    def tearDown(self):
        self.client.close();self.fixture.tearDown()

    def get(self,**params):
        return self.client.get('/api/v1/dashboard/ranking-history',params={**self.params,**params})

    def test_scores_only_two_days_bounded_read_only_and_cache(self):
        statements=[]
        def counter(*args):statements.append(args[2])
        event.listen(self.fixture.app.state.engine,'before_cursor_execute',counter)
        try:response=self.get()
        finally:event.remove(self.fixture.app.state.engine,'before_cursor_execute',counter)
        self.assertEqual(response.status_code,200,response.text)
        body=response.json()
        self.assertEqual(body['current']['reportDate'],'2026-10-08')
        self.assertEqual(body['baseline']['reportDate'],'2026-10-07')
        own=next(r for r in body['current']['rows'] if r['id']==CHILD_ID)
        self.assertEqual(own['total'],12)
        self.assertEqual(len(own['groups']),6)
        self.assertNotIn('parameters',response.text);self.assertNotIn('metrics',response.text)
        self.assertNotIn('private',response.text)
        self.assertTrue(all(s.lstrip().split()[0].upper() in ('SELECT','PRAGMA') for s in statements))
        self.assertLessEqual(len(statements),15)
        self.assertEqual(self.get().json(),body)
        self.assertGreater(self.fixture.app.state.daily_indicator_cache.stats().hits,0)
        print(f'RANKING_HISTORY sql={len(statements)} bytes={len(response.content)} writes=0')

    def test_national_totals_authoritative_not_rounded_group_sum(self):
        response=self.get(unit_id=ROOT_ID)
        self.assertEqual(response.status_code,200,response.text)
        rows=response.json()['current']['rows']
        self.assertEqual(len(rows),34)
        self.assertEqual(next(r for r in rows if r['id']==ROOT_ID)['total'],71)

    def test_missing_yesterday_not_replaced_and_exact_day_not_latest(self):
        body=self.get(report_date='2026-10-07').json()
        self.assertEqual(body['current']['reportDate'],'2026-10-07')
        self.assertIsNone(body['baseline'])
        self.assertIsNone(self.get(report_date='2026-10-09').json()['current'])
        self.assertEqual(self.get(report_date='2025-10-07').status_code,422)
        self.assertIsNone(self.get(year=2027).json()['current'])

    def test_selected_baseline_is_exact_and_validated(self):
        body=self.get(baseline_date='2026-10-07').json()
        self.assertEqual(body['baseline']['reportDate'],'2026-10-07')
        self.assertIsNone(self.get(baseline_date='2026-10-06').json()['baseline'])
        self.assertEqual(self.get(baseline_date='2026-10-08').status_code,422)
        self.assertEqual(self.get(baseline_date='2025-10-07').status_code,422)

    def test_authentication_and_agency_scope_before_cache(self):
        self.get(unit_id=ROOT_ID)
        with self.factory.begin() as db:
            account=db.get(UserAccount,self.fixture.user)
            account.access_tier='agency';account.unit_department_id=uuid.UUID(CHILD_ID)
        response=self.get();self.assertEqual(response.status_code,200,response.text)
        self.assertTrue(any(row['id']==str(self.fixture.peer) for row in response.json()['current']['rows']))
        self.assertEqual(self.get(unit_id=ROOT_ID).status_code,403)
        self.assertEqual(self.get(root_department_id=str(uuid.uuid4())).status_code,403)
        self.assertEqual(self.get(unit_id=str(uuid.uuid4())).status_code,403)
        self.client.cookies.clear();self.assertEqual(self.get().status_code,401)
