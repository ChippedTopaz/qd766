import json
import os
import sqlite3
import tempfile
import unittest
import uuid
from contextlib import closing
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch
from sqlalchemy import select, func, event
import test_trial_admin
from test_backend import ROOT_ID
from qd766.backend import admin_log_history as history
from qd766.backend.models import AdminAudit, UserAccount, SourceMonitorRun, SourceMonitorAlert, CollectionJob


class AdminLogHubTests(unittest.TestCase):
    def setUp(self):
        self.f=test_trial_admin.TrialAdminTests();self.f.setUp()
        self.temp=tempfile.TemporaryDirectory(dir=Path.cwd(),prefix='.tmp-log-hub-test-');self.root=Path(self.temp.name)
        self.patch=patch.object(history,'DAILY_ROOT',self.root);self.patch.start()
        self.now=datetime(2026,10,15,1,tzinfo=timezone.utc)
        self.target_id=uuid.uuid4()
        with self.f.app.state.session_factory.begin() as db:
            db.add(UserAccount(id=self.target_id,external_subject='log-target',email='target@example.test',display_name='Target <script>',trial_admitted=True))
            for i in range(23):
                db.add(AdminAudit(actor_id=self.f.admin_id,action='account.updated' if i%2 else 'trial-credit.updated',
                    created_at=datetime(2026,10,14,1,tzinfo=timezone.utc)+timedelta(minutes=i),
                    details={'accountId':str(self.target_id),'amount':i,'before':{'active':False,'password':'SECRET_BEFORE'},
                        'after':{'active':True,'token':'SECRET_AFTER'},'access_token':'SECRET_TOKEN','csrfToken':'SECRET_CSRF'}))
            db.add(SourceMonitorRun(day=date(2026,10,15),state='complete',details={'completed':['m1','m2'],'expected':2},updated_at=self.now))
        for i in range(9):self.checkpoint(date(2026,10,6)+timedelta(days=i))

    def tearDown(self):
        self.patch.stop();history._checkpoint.cache_clear()
        self.assertEqual(self.root.resolve().parent,Path.cwd().resolve())
        self.temp.cleanup();self.f.tearDown()

    def checkpoint(self,day,state='COMPLETE',number=102):
        directory=self.root/str(day);directory.mkdir(exist_ok=True)
        path=directory/'crawl_state.sqlite'
        with closing(sqlite3.connect(path)) as cp:
            cp.execute('CREATE TABLE blocks (block_key TEXT PRIMARY KEY,state TEXT,details TEXT)')
            cp.execute('INSERT INTO blocks VALUES (?,?,?)',('run-status',state,json.dumps({'expected':102,'completed':number})))
            for i in range(number):
                period=('year-2026-0','month-2026-10','quarter-2026-4')[i//34]
                key=f'daily:{day}:{period}:{uuid.UUID(int=i+1)}'
                cp.execute('INSERT INTO blocks VALUES (?,?,?)',(key,'SUCCESS',json.dumps({'province':f'Tỉnh {i}'})))
            for period in ('year-2026-0','month-2026-10','quarter-2026-4'):
                cp.execute('INSERT INTO blocks VALUES (?,?,?)',(f'daily:{day}:{period}:national','SUCCESS','{}'))
            cp.commit()
        os.utime(path,(self.now.timestamp(),self.now.timestamp()))

    def get(self,path):return self.f.client.get('/api/v1/admin/'+path)

    def test_today_102_blocks_national_and_real_sample_status(self):
        with self.f.app.state.session_factory() as db:report=history.today_report(db,now=self.now)
        self.assertEqual(report['day'],'2026-10-15');self.assertEqual(report['daily']['reportDate'],'2026-10-14')
        self.assertEqual(report['daily']['completed'],102);self.assertEqual(report['daily']['nationalCompleted'],3)
        self.assertEqual(len(report['daily']['phases']),3);self.assertNotIn('blocks',report['daily'])
        self.assertEqual(report['source']['state'],'complete');self.assertEqual(report['source']['completed'],2)
        self.assertFalse(report['needsRefresh']);self.assertEqual(report['alerts']['open'],0)
        (self.root/'2026-10-14'/'crawl_state.sqlite').unlink()
        with self.f.app.state.session_factory() as db:report=history.today_report(db,now=self.now)
        self.assertEqual(report['daily']['state'],'NOT_STARTED');self.assertNotEqual(report['daily']['state'],'COMPLETE')

    def test_history_pagination_dates_missing_days_and_issue_filter(self):
        with self.f.app.state.session_factory() as db:
            first=history.daily_page(db,1,None,None,None,False,now=self.now+timedelta(days=14))
            second=history.daily_page(db,2,None,None,None,False,now=self.now+timedelta(days=14))
            self.assertEqual(first['total'],23);self.assertEqual(len(first['items']),10);self.assertEqual(len(second['items']),10)
            self.assertGreater(first['items'][0]['runDate'],second['items'][0]['runDate'])
            self.assertTrue(all('blocks' not in i for i in first['items']))
        body=self.get('logs/daily?fromDate=2026-10-14&toDate=2026-10-15').json()
        self.assertEqual(body['total'],2);self.assertEqual(body['items'][0]['runDate'],'2026-10-15')
        self.assertEqual(body['items'][0]['reportDate'],'2026-10-14')
        self.assertEqual(self.get('logs/daily?fromDate=2026-10-16&toDate=2026-10-01').status_code,422)
        self.assertEqual(self.get('logs/daily?fromDate=bad').status_code,422)
        with self.f.app.state.session_factory() as db:
            filtered=history.daily_page(db,1,date(2026,10,15),date(2026,10,15),None,True,now=self.now)
            self.assertEqual(filtered['total'],0)
        with self.f.app.state.session_factory.begin() as db:
            db.add(SourceMonitorAlert(kind='structure',title='Changed',dedupe_key='log-test',details={'contexts':[{'reportDate':'2026-10-14'}]},created_at=self.now,updated_at=self.now))
        with self.f.app.state.session_factory() as db:
            filtered=history.daily_page(db,1,date(2026,10,15),date(2026,10,15),None,True,now=self.now)
            self.assertEqual(filtered['total'],1);self.assertEqual(filtered['items'][0]['alerts'],1)

    def test_detail_10_rows_query_bounds_and_no_checkpoint_writes(self):
        path=self.root/'2026-10-14'/'crawl_state.sqlite';before=path.read_bytes()
        report=self.get('logs/daily/2026-10-14').json()
        self.assertEqual(report['total'],105);self.assertEqual(len(report['items']),10)
        self.assertEqual(len(self.get('logs/daily/2026-10-14?page=11').json()['items']),5)
        self.assertEqual(self.get('logs/daily/2026-10-14?state=issues').json()['total'],0)
        self.assertEqual(path.read_bytes(),before)
        self.assertEqual(self.get('logs/daily/2026-10-14?page=0').status_code,422)
        self.assertEqual(self.get('logs/daily/../../.env').status_code,404)
        self.assertEqual(self.get('logs/daily/2099-01-01').status_code,404)

    def test_corrupt_checkpoint_stale_running_and_invalid_complete(self):
        p=self.root/'2026-10-14'/'crawl_state.sqlite';p.write_bytes(b'not sqlite')
        self.assertEqual(history.daily_record(date(2026,10,14),now=self.now)['state'],'UNREADABLE')
        self.checkpoint(date(2026,10,5),state='COMPLETE',number=1)
        self.assertEqual(history.daily_record(date(2026,10,5),now=self.now)['state'],'INCOMPLETE')
        self.checkpoint(date(2026,10,4),state='RUNNING',number=1)
        p=self.root/'2026-10-4'/'crawl_state.sqlite'
        self.assertEqual(history.daily_record(date(2026,10,4),now=self.now+timedelta(hours=1))['state'],'NEEDS_CHECK')

    def test_audit_pagination_search_before_after_and_secret_redaction(self):
        first=self.get('audit?page=1').json();self.assertEqual(first['total'],23);self.assertEqual(len(first['items']),10)
        self.assertEqual(len(self.get('audit?page=3').json()['items']),3)
        self.assertNotIn('details',first['items'][0]);self.assertEqual(first['items'][0]['actor'],'Owner')
        self.assertEqual(first['items'][0]['targetEmail'],'target@example.test')
        detail=self.get('audit/'+first['items'][0]['id']).json()
        self.assertEqual(detail['details']['after'],{'active':True});self.assertEqual(detail['details']['before'],{'active':False})
        self.assertNotIn('SECRET',json.dumps(detail))
        self.assertEqual(self.get('audit?page=1&search=target%40example.test').json()['total'],23)
        self.assertEqual(self.get('audit?page=1&search=SECRET_TOKEN').json()['total'],0)
        self.assertEqual(self.get('audit?page=1&search=%25').json()['total'],0)
        self.assertEqual(self.get('audit?page=1&action=account.updated').json()['total'],11)
        self.assertEqual(self.get('audit?page=1&fromDate=2026-10-15').json()['total'],0)
        self.assertEqual(self.get('audit?page=1&actorId=bad').status_code,422)
        self.assertEqual(self.get('audit?page=1&fromDate=2026-10-15&toDate=2026-10-14').status_code,422)

    def test_admin_only_read_only_no_wallet_queue_or_audit_mutation(self):
        queries=[];engine=self.f.app.state.engine
        listener=lambda *args:queries.append(args[2]);event.listen(engine,'before_cursor_execute',listener)
        try:
            for path in ('logs/today','logs/daily','logs/daily/2026-10-14','logs/archive?kind=batches','audit?page=1','collection-log?compact=true&limit=10'):
                self.assertEqual(self.get(path).status_code,200,path)
            self.assertFalse(any(s.lstrip().upper().startswith(('INSERT','UPDATE','DELETE')) for s in queries))
        finally:event.remove(engine,'before_cursor_execute',listener)
        with self.f.app.state.session_factory() as db:
            self.assertEqual(db.scalar(select(func.count()).select_from(AdminAudit)),23)
            self.assertEqual(db.scalar(select(func.count()).select_from(CollectionJob)),0)
            self.assertEqual(db.get(UserAccount,self.f.admin_id).credit_balance,0)
        with self.f.app.state.session_factory.begin() as db:db.get(UserAccount,self.f.admin_id).role='user'
        for path in ('logs/today','logs/daily','logs/archive?kind=batches','audit?page=1'):
            self.assertEqual(self.get(path).status_code,403)
        self.f.client.cookies.clear();self.assertEqual(self.get('logs/today').status_code,401)

    def test_compact_jobs_filters_do_not_scan_checkpoint_history(self):
        from qd766.backend.jobs import enqueue_job
        with self.f.app.state.session_factory.begin() as db:
            enqueue_job(db,{'kind':'evaluation-snapshot','rootDepartmentId':ROOT_ID,'scope':'all',
                'period':{'type':'month','year':2026,'month':10}})
        with patch.object(history,'_checkpoint',side_effect=AssertionError('Must not read historical files for jobs')):
            r=self.get('collection-log?compact=true&source=system&limit=10&periodType=month&year=2026&periodValue=10')
            self.assertEqual(r.status_code,200,r.text);self.assertEqual(r.json()['total'],1)
            self.assertEqual(r.json()['daily'],[]);self.assertIsNone(r.json()['probe']);self.assertEqual(r.json()['batches'],[])
            self.assertEqual(self.get('collection-log?compact=true&periodType=quarter&periodValue=5').status_code,422)

    def test_log_stylesheet_is_allowed_without_opening_other_static_paths(self):
        from fastapi.staticfiles import StaticFiles
        web=Path(__file__).resolve().parents[1]/'web'
        self.f.app.mount('/',StaticFiles(directory=str(web),html=True),name='test-log-static')
        self.f.client.cookies.clear()
        response=self.f.client.get('/admin-logs.css?v=log-refine-20261015')
        self.assertEqual(response.status_code,200,response.text)
        self.assertIn('text/css',response.headers['content-type'])
        self.assertIn('.log-filter-primary',response.text)
        for path in ('/.env','/admin-logs.css.bak','/daily-combo-preview.html'):
            self.assertEqual(self.f.client.get(path).status_code,403,path)


if __name__=='__main__':unittest.main()
