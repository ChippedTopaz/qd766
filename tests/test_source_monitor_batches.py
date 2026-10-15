import unittest
from datetime import datetime,timezone
from sqlalchemy import select,func,event
from sqlalchemy.dialects import postgresql
from qd766.backend.source_monitor import alert
from qd766.backend.source_monitor_batches import batch_query
from qd766.backend.models import SourceMonitorAlert,Base,AdminAudit,UserAccount
import test_trial_admin


class SourceBatchTests(unittest.TestCase):
    def setUp(self):
        self.f=test_trial_admin.TrialAdminTests();self.f.setUp()
        self.url='/api/v1/admin/source-monitor'
        self.factory=self.f.app.state.session_factory
        with self.factory.begin() as db:
            for i in range(23):
                batch={'id':'daily:2026-10-14','day':'2026-10-15','label':'Cào dữ liệu · 05:00','source':'daily'}
                alert(db,'structure' if i%2 else 'closed-period',f'Nội dung {i}',[i],
                    {'batch':batch,'changeCount':2,'changes':[]})
            alert(db,'check-failed','Đợt 6h',['six'],{'scheduledAt':'06:00 Asia/Ho_Chi_Minh'},now=datetime(2026,10,15,tzinfo=timezone.utc))

    def tearDown(self):self.f.tearDown()

    def get(self,path='?grouped=true'):
        r=self.f.client.get(self.url+path);self.assertEqual(r.status_code,200,r.text);return r.json()

    def test_one_notice_per_run_with_full_totals_and_member_pagination(self):
        sql=[];engine=self.f.app.state.engine;listener=lambda *a:sql.append(a[2]);event.listen(engine,'before_cursor_execute',listener)
        try:
            report=self.get();self.assertEqual(report['total'],2);self.assertEqual(report['unread'],2)
            daily=next(i for i in report['items'] if i['id'].startswith('daily:'))
            self.assertEqual(daily['contentCount'],23);self.assertEqual(daily['changeCount'],46)
            self.assertEqual(daily['kinds']['structure'],11)
            detail=self.get('/batches/detail?batchId='+daily['id']);self.assertEqual(len(detail['items']),10)
            second=self.get('/batches/detail?batchId='+daily['id']+'&page=2')
            self.assertEqual(len(second['items']),10)
            self.assertFalse({i['id'] for i in detail['items']}&{i['id'] for i in second['items']})
            last=self.get('/batches/detail?batchId='+daily['id']+'&page=999');self.assertEqual(last['page'],3);self.assertEqual(len(last['items']),3)
            self.assertEqual(self.get('?grouped=true&kind=structure')['total'],1)
            self.assertEqual(self.get('?grouped=true&fromDate=2099-01-01')['total'],0)
            self.assertFalse(any(s.lstrip().upper().startswith(('INSERT','UPDATE','DELETE')) for s in sql))
        finally:event.remove(engine,'before_cursor_execute',listener)
        self.assertIn('GROUP BY',str(batch_query().compile(dialect=postgresql.dialect())))

    def test_batch_read_keeps_per_content_resolution_and_requires_admin_csrf(self):
        body={'batchId':'daily:2026-10-14'};path=self.url+'/batches/read'
        self.assertEqual(self.f.client.post(path,json=body).status_code,403)
        r=self.f.client.post(path,json=body,headers=self.f.headers);self.assertEqual(r.status_code,200,r.text)
        self.assertEqual(r.json()['updated'],23);self.assertFalse(r.json()['published'])
        self.assertEqual(self.get()['unread'],1);self.assertEqual(self.get()['openCount'],2)
        members=self.get('/batches/detail?batchId=daily:2026-10-14')['items']
        self.assertTrue(all(i['read'] and not i['resolved'] for i in members))
        self.f.client.post(self.url+'/'+members[0]['id']+'/review',json={'action':'resolve','note':'Đã xác minh'},headers=self.f.headers)
        self.assertEqual(self.get('/batches/detail?batchId=daily:2026-10-14')['openCount'],22)
        self.assertEqual(self.get('?grouped=true&state=resolved')['total'],0,'Partially resolved batch remains open')
        with self.factory() as db:
            self.assertEqual(db.scalar(select(func.count()).select_from(AdminAudit)),2)
            for name in ('collection_jobs','credit_wallet_events','formula_config_revisions'):
                self.assertEqual(db.scalar(select(func.count()).select_from(Base.metadata.tables[name])),0)
        with self.factory.begin() as db:db.get(UserAccount,self.f.admin_id).role='user'
        self.assertEqual(self.f.client.get(self.url+'/batches/detail?batchId=daily:2026-10-14').status_code,403)
        self.assertEqual(self.f.client.post(path,json=body,headers=self.f.headers).status_code,403)
        self.f.client.cookies.clear()
        self.assertEqual(self.f.client.get(self.url+'?grouped=true').status_code,401)
        self.assertEqual(self.f.client.get(self.url+'/batches/detail?batchId=daily:2026-10-14').status_code,401)

    def test_missing_invalid_inputs_and_batch_paging(self):
        for suffix in ('/batches/detail?batchId=missing','/batches/detail?batchId='):
            self.assertIn(self.f.client.get(self.url+suffix).status_code,(404,422))
        self.assertEqual(self.f.client.get(self.url+'?grouped=true&kind=unknown').status_code,422)
        with self.factory.begin() as db:
            for i in range(12):alert(db,'structure','Old record',[str(i),'old'],{'changeCount':1})
        report=self.get();self.assertEqual(report['total'],14);self.assertEqual(len(report['items']),10)
        self.assertEqual(len(self.get('?grouped=true&page=2')['items']),4)
        self.assertTrue(any(i['label']=='Giữ nguyên cảnh báo cũ' for i in report['items']))

    def test_run_dedupe_across_provinces_but_not_days_or_lanes(self):
        with self.factory.begin() as db:
            details={'contexts':[{'rootId':'a','reportDate':'2026-10-14'}],'changeCount':1}
            a=alert(db,'structure','Change',['same'],details);db.flush()
            b=alert(db,'structure','Change',['same'],{'contexts':[{'rootId':'b','reportDate':'2026-10-14'}],'changeCount':1});db.flush()
            self.assertEqual(a.id,b.id);self.assertEqual(b.occurrences,2)
            self.assertEqual(len(b.details['contexts']),2)
            c=alert(db,'structure','Change',['same'],{'contexts':[{'rootId':'a','reportDate':'2026-10-15'}],'changeCount':1});db.flush()
            d=alert(db,'structure','Change',['same'],{'contexts':[{'rootId':'a','checkDate':'2026-10-15'}],'changeCount':1});db.flush()
            self.assertNotEqual(a.id,c.id);self.assertNotEqual(a.id,d.id)
            self.assertEqual(a.details['batch']['id'],'daily:2026-10-14')
            self.assertEqual(a.details['batch']['day'],'2026-10-15')
            self.assertEqual(d.details['batch']['id'],'monitor:2026-10-15')


if __name__=='__main__':unittest.main()
