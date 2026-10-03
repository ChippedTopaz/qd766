import sys,unittest,uuid
from pathlib import Path
from datetime import datetime,timedelta,timezone
from types import SimpleNamespace
from sqlalchemy import select,func
from fastapi.testclient import TestClient
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from qd766.backend import create_app
from qd766.backend.config import Settings
from qd766.backend.models import Base,Department,Formality,Snapshot,UserAccount,LoginSession,CollectionJob,PaidDataRequest,CreditLedgerEntry,CollectionControl
from qd766.backend.auth import digest
from qd766.backend.paid_requests import top_up_credits,settle_paid_requests_for_job,refund_blocked_paid_requests
from qd766.province_roots import load_province_roots

class UserCollectionTest(unittest.TestCase):
    def setUp(self):
        self.app=create_app(Settings(database_url='sqlite+pysqlite://',public_read_only=True,require_login=True,
            google_client_id='test',google_client_secret='test-secret',google_redirect_uri='https://example.test/api/v1/auth/google/callback',
            paid_requests_enabled=True,formality_credit_cost=3,trial_credits_enabled=True))
        Base.metadata.create_all(self.app.state.engine)
        self.factory=self.app.state.session_factory
        self.root=next(r for r in load_province_roots().values() if r.province_name=='Phú Thọ')
        self.ids=[uuid.uuid4(),uuid.uuid4()];self.formality=uuid.uuid4();self.second=uuid.uuid4()
        self.items=[SimpleNamespace(id=str(i),code=f'2.00000{n}',name=f'TTHC {n}',field='Kiểm thử') for n,i in enumerate([self.formality,self.second])]
        self.app.state.province_catalog_client=SimpleNamespace(load=lambda *a,**k:SimpleNamespace(select=lambda **k:self.items))
        with self.factory.begin() as db:
            db.add(Department(id=self.root.root_department_id,name=self.root.department_name,code=self.root.department_code,attributes={}))
            for n,aid in enumerate(self.ids):
                db.add(UserAccount(id=aid,external_subject=f'test-{n}',display_name=f'User {n}',plan='free',root_department_id=self.root.root_department_id))
                db.flush();top_up_credits(db,aid,10,event_key=f'top-{n}')
                db.add(LoginSession(token_hash=digest(f'session-{n}'),account_id=aid,csrf_token=f'csrf-{n}',expires_at=datetime.now(timezone.utc)+timedelta(hours=1)))
        self.clients=[TestClient(self.app),TestClient(self.app)]
        for n,c in enumerate(self.clients):c.cookies.set('qd766_session',f'session-{n}')
        self.selection={'periodType':'year','year':2026,'periodValue':None,'formalityIds':[str(self.formality)]}
    def tearDown(self):self.app.state.engine.dispose()
    def quote(self,n=0,selection=None):return self.clients[n].post('/api/v1/me/collection-quote',json=selection or self.selection,headers={'X-QD766-CSRF':f'csrf-{n}'})
    def submit(self,n=0,quote=None,token=None):
        return self.clients[n].post('/api/v1/me/formality-requests',json={'quote':quote or self.quote(n).json()['quote'],'token':token or str(uuid.uuid4())},headers={'X-QD766-CSRF':f'csrf-{n}'})
    def settle(self):
        with self.factory.begin() as db:
            snapshot=Snapshot(snapshot_key='shared',schema_version=1,root_department_id=self.root.root_department_id,
                period_type='year',year=2026,scope='formality',formality_id=self.formality,state='complete',policy={},status_detail={})
            db.add(snapshot);db.flush();job=db.scalar(select(CollectionJob));job.state='succeeded'
            settle_paid_requests_for_job(db,job,snapshot)
    def test_own_library_survives_session_and_other_account_must_pay(self):
        first=self.submit();self.assertEqual(first.status_code,202)
        self.assertEqual(first.json()['availableCredits'],7)
        self.settle()
        url='/api/v1/me/formalities?period_type=year&year=2026'
        self.assertEqual(len(self.clients[0].get(url).json()['items']),1)
        self.assertEqual(self.clients[1].get(url).json()['items'],[])
        self.assertEqual(self.quote(1).json()['totalCredits'],3)
        result=self.submit(1);self.assertEqual(result.status_code,202);self.assertEqual(result.json()['items'][0]['state'],'ready')
        self.assertEqual(result.json()['availableCredits'],7)
        self.assertEqual(self.quote(0).json()['totalCredits'],0)
        self.submit(0)
        with self.factory() as db:
            self.assertEqual(db.scalar(select(func.count()).select_from(CollectionJob)),1)
            self.assertEqual(db.scalar(select(func.count()).select_from(PaidDataRequest)),2)
            self.assertEqual(db.get(UserAccount,self.ids[0]).credit_balance,7)
    def test_two_users_share_queued_job_and_token_replay(self):
        quote=self.quote().json()['quote'];token=str(uuid.uuid4())
        self.submit(quote=quote,token=token);self.submit(quote=quote,token=token);self.submit(1)
        with self.factory() as db:
            self.assertEqual(db.scalar(select(func.count()).select_from(CollectionJob)),1)
            self.assertEqual(db.scalar(select(func.count()).select_from(PaidDataRequest)),2)
    def test_csrf_cross_account_and_tampered_quote(self):
        self.assertEqual(self.clients[0].post('/api/v1/me/collection-quote',json=self.selection).status_code,403)
        quote=self.quote().json()['quote']
        self.assertEqual(self.submit(1,quote=quote).status_code,403)
        self.assertEqual(self.submit(quote=quote+'x').status_code,409)
        self.assertEqual(TestClient(self.app).get('/api/v1/me/formality-requests').status_code,401)
    def test_selection_denied_before_cache_and_wrong_period_denied(self):
        self.submit();self.settle()
        url=f'/api/v1/dashboard/selection?scope=formality&period_type=year&year=2026&formality_id={self.formality}'
        self.assertEqual(self.clients[0].get(url).status_code,200)
        self.assertEqual(self.clients[1].get(url).status_code,403)
        self.assertEqual(self.clients[0].get(url.replace('year=2026','year=2025')).status_code,403)
        for path in ['/api/v1/snapshots','/api/v1/collection-jobs','/api/v1/formality-batches','/api/v1/dashboard/formalities']:
            self.assertEqual(self.clients[0].get(path).status_code,403)
    def test_unknown_formality_and_atomic_credit_failure(self):
        self.assertEqual(self.quote(selection={**self.selection,'formalityIds':[str(uuid.uuid4())]}).status_code,422)
        with self.factory.begin() as db:db.get(UserAccount,self.ids[0]).credit_balance=5
        quote=self.quote(selection={**self.selection,'formalityIds':[str(self.formality),str(self.second)]}).json()['quote']
        self.assertEqual(self.submit(quote=quote).status_code,409)
        with self.factory() as db:
            self.assertEqual(db.scalar(select(func.count()).select_from(CollectionJob)),0)
            self.assertEqual(db.scalar(select(func.count()).select_from(PaidDataRequest)),0)
            self.assertEqual(db.get(UserAccount,self.ids[0]).credit_balance,5)
    def test_circuit_releases_reserved_credit_without_new_jobs(self):
        self.submit()
        with self.factory.begin() as db:
            db.add(CollectionControl(key='dvcqg',circuit_state='open'));db.flush()
            self.assertEqual(refund_blocked_paid_requests(db),1)
        with self.factory() as db:
            self.assertEqual(db.get(UserAccount,self.ids[0]).credit_balance,10)
            self.assertEqual(db.get(UserAccount,self.ids[0]).credit_reserved,0)
            self.assertEqual(db.scalar(select(PaidDataRequest)).state,'refunded')
    def test_public_css_and_defaults_remain_closed(self):
        self.assertEqual(self.clients[0].get('/bento.css').status_code,200)
        with self.assertRaises(ValueError):create_app(Settings(paid_requests_enabled=True))
    def test_credit_lock_refreshes_cached_account_balance(self):
        from qd766.backend.paid_requests import _locked_account
        with self.factory() as old_session:
            old=old_session.get(UserAccount,self.ids[0]);self.assertEqual(old.credit_balance,10)
            with self.factory.begin() as new_session:
                top_up_credits(new_session,self.ids[0],5,event_key='concurrent-topup')
            self.assertEqual(_locked_account(old_session,self.ids[0]).credit_balance,15)
    def test_notifications_persist_and_acknowledgement_is_account_scoped(self):
        first=self.submit().json()['items'][0]['id'];self.settle();self.submit(1)
        self.assertEqual(self.clients[0].get('/api/v1/me/formality-requests').json()['unreadNotifications'],1)
        self.clients[1].post('/api/v1/me/notifications/read',json={'requestIds':[first]},headers={'X-QD766-CSRF':'csrf-1'})
        self.assertEqual(self.clients[0].get('/api/v1/me/formality-requests').json()['unreadNotifications'],1)
        result=self.clients[0].post('/api/v1/me/notifications/read',json={'requestIds':[first]},headers={'X-QD766-CSRF':'csrf-0'})
        self.assertEqual(result.status_code,200)
        self.assertEqual(self.clients[0].get('/api/v1/me/formality-requests').json()['unreadNotifications'],0)
