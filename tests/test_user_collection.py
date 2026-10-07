import sys,unittest,uuid
from pathlib import Path
from datetime import datetime,timedelta,timezone
from types import SimpleNamespace
from sqlalchemy import select,func
from fastapi.testclient import TestClient
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from qd766.backend import create_app
from qd766.backend.config import Settings
from qd766.backend.models import AccountCollectionPermission,Base,Department,Formality,Snapshot,UserAccount,LoginSession,CollectionJob,PaidDataRequest,CreditLedgerEntry,CollectionControl
from qd766.backend.auth import digest
from qd766.backend.paid_requests import top_up_credits,settle_paid_requests_for_job,refund_blocked_paid_requests
from qd766.province_roots import load_province_roots

class UserCollectionTest(unittest.TestCase):
    def nationwide_fixture(self,role='admin'):
        hue=next(r for r in load_province_roots().values() if r.province_name=='Huế')
        with self.factory.begin() as db:
            if db.get(Department,hue.root_department_id) is None:
                db.add(Department(id=hue.root_department_id,name=hue.department_name,attributes={}))
            account=db.get(UserAccount,self.ids[0]);account.role=role;account.trial_admitted=True
            account.access_tier='national' if role=='user' else 'province'
        for item in self.items:
            item.publishing_agency='Test';item.execution_levels=('province','ward')
        self.app.state.province_catalog_client=SimpleNamespace(load=lambda code,**k:SimpleNamespace(
            province=SimpleNamespace(code=code,name='Test'),fields=['Test'],select=lambda **k:self.items))
        return hue

    def test_admin_and_national_catalog_follow_selected_province(self):
        for role in ('admin','user'):
            hue=self.nationwide_fixture(role)
            response=self.clients[0].get(f'/api/v1/province-catalog/{hue.province_code}/preview?period_type=year&year=2026')
            self.assertEqual(response.status_code,200,response.text)
            self.assertEqual(response.json()['province']['code'],hue.province_code)
            if role=='user':self.assertEqual(self.clients[0].get('/api/v1/admin/accounts').status_code,403)

    def test_province_and_agency_cannot_forge_selected_province(self):
        hue=self.nationwide_fixture()
        for tier in ('province','agency'):
            with self.factory.begin() as db:
                account=db.get(UserAccount,self.ids[0]);account.role='user';account.access_tier=tier
                if tier=='agency':
                    child=uuid.uuid4();db.add(Department(id=child,name='Test ward',attributes={}));account.unit_department_id=child
            own=self.clients[0].get(f'/api/v1/province-catalog/{self.root.province_code}/preview?period_type=year&year=2026')
            self.assertEqual(own.status_code,200,own.text)
            self.assertEqual(self.quote(selection={**self.selection,'rootDepartmentId':str(hue.root_department_id)}).status_code,403)
            for path in ('/api/v1/me/formalities?period_type=year&year=2026&','/api/v1/me/formality-requests?'):
                self.assertEqual(self.clients[0].get(path+'root_department_id='+str(hue.root_department_id)).status_code,403)
            self.assertEqual(self.clients[0].get(f'/api/v1/province-catalog/{hue.province_code}/preview?period_type=year&year=2026').status_code,403)
        with self.factory() as db:
            self.assertEqual(db.get(UserAccount,self.ids[0]).credit_balance,10)
            self.assertEqual(db.scalar(select(func.count()).select_from(PaidDataRequest)),0)

    def test_nationwide_ownership_and_credit_are_separate_per_province(self):
        for role in ('admin','user'):
            self.nationwide_fixture(role)
            self.assertEqual(self.quote().status_code,200)
        self.assertEqual(self.submit().status_code,202);self.settle()
        hue=self.nationwide_fixture()
        params={'scope':'formality','period_type':'year','year':2026,'root_department_id':str(self.root.root_department_id),'formality_id':str(self.formality)}
        self.assertEqual(self.clients[0].get('/api/v1/dashboard/selection',params=params).status_code,200)
        with self.factory.begin() as db:
            another=db.get(UserAccount,self.ids[1]);another.access_tier='national';another.trial_admitted=True
        self.assertEqual(self.clients[1].get('/api/v1/dashboard/selection',params=params).status_code,403)
        selection={**self.selection,'rootDepartmentId':str(hue.root_department_id)}
        own=self.quote().json();other=self.quote(selection=selection).json()
        self.assertEqual(own['totalCredits'],0);self.assertEqual(other['totalCredits'],3)
        self.assertEqual(self.clients[0].get('/api/v1/me/formalities?period_type=year&year=2026&root_department_id='+str(hue.root_department_id)).json()['items'],[])
        quote=other['quote'];token=str(uuid.uuid4())
        response=self.submit(quote=quote,token=token)
        self.assertEqual(response.status_code,202,response.text)
        self.assertEqual(response.json()['availableCredits'],4)
        self.assertEqual(response.json()['items'][0]['rootDepartmentId'],str(hue.root_department_id))
        self.assertEqual(self.submit(quote=quote,token=token).json()['availableCredits'],4)
        for root in (self.root,hue):
            history=self.clients[0].get('/api/v1/me/formality-requests?root_department_id='+str(root.root_department_id)).json()['items']
            self.assertEqual(len(history),1);self.assertEqual(history[0]['rootDepartmentId'],str(root.root_department_id))
        denied=self.clients[0].get('/api/v1/dashboard/selection',params={'scope':'formality','period_type':'year','year':2026,'root_department_id':str(hue.root_department_id),'formality_id':str(self.formality)})
        self.assertEqual(denied.status_code,403)
        with self.factory() as db:
            self.assertEqual(db.scalar(select(func.count()).select_from(PaidDataRequest)),2)
            self.assertEqual(db.get(UserAccount,self.ids[0]).root_department_id,self.root.root_department_id)

    def test_nationwide_quote_denied_after_scope_revoked(self):
        hue=self.nationwide_fixture()
        quote=self.quote(selection={**self.selection,'rootDepartmentId':str(hue.root_department_id)}).json()['quote']
        with self.factory.begin() as db:
            account=db.get(UserAccount,self.ids[0]);account.role='user';account.access_tier='province'
        self.assertEqual(self.submit(quote=quote).status_code,403)
        with self.factory() as db:
            self.assertEqual(db.get(UserAccount,self.ids[0]).credit_balance,10)
            self.assertEqual(db.scalar(select(func.count()).select_from(PaidDataRequest)),0)

    def test_nationwide_quote_root_binding_and_unknown_province(self):
        from qd766.backend.user_collection import encode_quote,decode_quote
        hue=self.nationwide_fixture()
        request=SimpleNamespace(app=self.app)
        quote=self.quote(selection={**self.selection,'rootDepartmentId':str(hue.root_department_id)}).json()['quote']
        claims=decode_quote(request,quote);claims['root']=str(self.root.root_department_id)
        self.assertEqual(self.submit(quote=encode_quote(request,claims)).status_code,403)
        self.assertEqual(self.quote(selection={**self.selection,'rootDepartmentId':str(uuid.uuid4())}).status_code,404)
        self.assertEqual(self.quote(selection={**self.selection,'rootDepartmentId':'invalid'}).status_code,422)
        conflict=self.clients[0].get('/api/v1/me/formality-requests',params=[('root_department_id',str(self.root.root_department_id)),('root_department_id',str(hue.root_department_id))])
        self.assertEqual(conflict.status_code,422)
        with self.factory() as db:
            self.assertEqual(db.get(UserAccount,self.ids[0]).credit_balance,10)
            self.assertEqual(db.scalar(select(func.count()).select_from(PaidDataRequest)),0)

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
                db.add(AccountCollectionPermission(account_id=aid,enabled=True))
                db.add(LoginSession(token_hash=digest(f'session-{n}'),account_id=aid,csrf_token=f'csrf-{n}',expires_at=datetime.now(timezone.utc)+timedelta(hours=1)))
        self.clients=[TestClient(self.app),TestClient(self.app)]
        for n,c in enumerate(self.clients):c.cookies.set('qd766_session',f'session-{n}')
        self.selection={'periodType':'year','year':2026,'periodValue':None,'formalityIds':[str(self.formality)]}
    def tearDown(self):self.app.state.engine.dispose()
    def test_pause_blocks_quote_and_previously_signed_confirmation_without_hold(self):
        headers={'X-QD766-CSRF':'csrf-0'}
        quote=self.clients[0].post('/api/v1/me/collection-quote',json=self.selection,headers=headers)
        self.assertEqual(quote.status_code,200)
        self.factory.configure(info={"wallet_requests_paused":True})
        blocked=self.clients[0].post('/api/v1/me/collection-quote',json=self.selection,headers=headers)
        self.assertEqual(blocked.status_code,503)
        submit=self.clients[0].post('/api/v1/me/formality-requests',json={
            'quote':quote.json()['quote'],'token':str(uuid.uuid4())},headers=headers)
        self.assertEqual(submit.status_code,503)
        with self.factory() as db:
            self.assertEqual(db.get(UserAccount,self.ids[0]).credit_balance,10)
            self.assertEqual(db.scalar(select(func.count()).select_from(PaidDataRequest)),0)
            self.assertEqual(db.scalar(select(func.count()).select_from(CollectionJob)),0)
    def source_wallet(self,n=0,active=True):
        from qd766.backend.wallet_access import enroll
        from qd766.backend.credit_wallet import grant
        from qd766.backend.models import SubscriptionCycle
        self.factory.configure(info={"source_wallet_enabled":True})
        now=datetime.now(timezone.utc)
        with self.factory.begin() as db:
            enroll(db,self.ids[n],now=now)
            grant(db,self.ids[n],2,source="subscription",operation_key="seed-sub",now=now,expires_at=now+timedelta(days=1))
            grant(db,self.ids[n],600,source="purchased",operation_key="seed-purchased",now=now)
            if active:
                db.add(SubscriptionCycle(account_id=self.ids[n],operation_key="fixture",tier="province",
                    origin="redemption",starts_at=now,ends_at=now+timedelta(days=30),included_credit=0))

    def test_source_wallet_shared_job_charges_each_account_and_legacy_is_untouched(self):
        self.source_wallet(0);self.source_wallet(1)
        self.assertEqual(self.submit(0).json()["availableCredits"],599)
        self.assertEqual(self.submit(1).json()["reservedCredits"],3)
        with self.factory() as db:self.assertEqual(db.scalar(select(func.count()).select_from(CollectionJob)),1)
        self.settle()
        for n in (0,1):
            wallet=self.clients[n].get("/api/v1/me/credits").json()
            self.assertEqual((wallet["subscriptionCredits"],wallet["purchasedCredits"],wallet["reservedCredits"]),(0,599,0))
            self.assertEqual(wallet["legacyCredits"],10)
            self.assertEqual(self.clients[n].get("/api/v1/auth/me").json()["credits"],599)
            self.assertEqual(self.submit(n).json()["availableCredits"],599)
        with self.factory() as db:
            from qd766.backend.models import CreditWalletEvent
            self.assertEqual(db.scalar(select(func.count()).select_from(CreditWalletEvent).where(CreditWalletEvent.kind=="charge")),2)

    def test_source_wallet_failure_refunds_correct_sources_with_seven_day_extension(self):
        self.source_wallet()
        response=self.submit();self.assertEqual(response.status_code,202)
        with self.factory.begin() as db:
            from qd766.backend.models import CreditLot
            from qd766.backend.paid_requests import refund_paid_requests_for_job
            lot=db.scalar(select(CreditLot).where(CreditLot.account_id==self.ids[0],CreditLot.source=="subscription"))
            lot.expires_at=datetime.now(timezone.utc)-timedelta(seconds=1);db.flush()
            refund_paid_requests_for_job(db,db.scalar(select(CollectionJob)),{"kind":"simulated-failure"})
        wallet=self.clients[0].get("/api/v1/me/credits").json()
        self.assertEqual((wallet["subscriptionCredits"],wallet["purchasedCredits"],wallet["reservedCredits"]),(2,600,0))
        self.assertEqual(wallet["legacyCredits"],10)
        expiry=datetime.fromisoformat(wallet["creditExpirations"][0]["at"])
        self.assertAlmostEqual((expiry-datetime.now(timezone.utc)).total_seconds(),7*86400,delta=5)

    def test_redemption_api_csrf_scope_and_repeat(self):
        self.source_wallet(active=False)
        token=str(uuid.uuid4());payload={"token":token,"expectedCost":600}
        url="/api/v1/me/subscription/redemption"
        self.assertEqual(self.clients[0].post(url,json=payload).status_code,403)
        self.assertEqual(self.clients[0].post(url,json={**payload,"expectedCost":300},headers={"X-QD766-CSRF":"csrf-0"}).status_code,409)
        result=self.clients[0].post(url,json=payload,headers={"X-QD766-CSRF":"csrf-0"})
        self.assertEqual(result.status_code,200)
        self.assertEqual(result.json()["availableCredits"],2)
        replay=self.clients[0].post(url,json=payload,headers={"X-QD766-CSRF":"csrf-0"})
        self.assertEqual(replay.status_code,200)
        self.assertEqual(self.clients[0].get("/api/v1/me/credits").json()["purchasedCredits"],0)
        self.assertEqual(self.clients[1].post(url,json=payload,headers={"X-QD766-CSRF":"csrf-1"}).status_code,403)

    def test_source_wallet_enrollment_rejects_pending_and_expired_subscription_blocks_new_request(self):
        self.submit()
        from qd766.backend.wallet_access import enroll
        from qd766.backend.credit_wallet import WalletError
        self.factory.configure(info={"source_wallet_enabled":True})
        with self.factory.begin() as db:
            with self.assertRaises(WalletError):enroll(db,self.ids[0],now=datetime.now(timezone.utc))
        self.source_wallet(1,active=False)
        self.assertEqual(self.quote(1).status_code,403)

    def test_expired_subscription_keeps_library_and_free_reopen_but_blocks_paid_quote(self):
        self.source_wallet()
        self.submit();self.settle()
        from qd766.backend.models import SubscriptionCycle
        now=datetime.now(timezone.utc)
        with self.factory.begin() as db:
            cycle=db.scalar(select(SubscriptionCycle).where(SubscriptionCycle.account_id==self.ids[0]))
            cycle.starts_at=now-timedelta(days=31);cycle.ends_at=now-timedelta(seconds=1)
        self.assertEqual(len(self.clients[0].get('/api/v1/me/formalities?period_type=year&year=2026').json()['items']),1)
        own=self.quote();self.assertEqual(own.status_code,200)
        self.assertEqual(own.json()["totalCredits"],0)
        self.assertEqual(self.submit(quote=own.json()["quote"]).json()["availableCredits"],599)
        new=self.quote(selection={**self.selection,'formalityIds':[str(self.second)]})
        self.assertEqual(new.status_code,403)
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
        waiting_quote=self.quote().json()["items"][0]
        self.assertTrue(waiting_quote["owned"])
        self.assertEqual(waiting_quote["ownedState"],"waiting")
        self.assertEqual(waiting_quote["cost"],0)
        self.settle()
        self.assertEqual(self.quote().json()["items"][0]["ownedState"],"ready")
        url='/api/v1/me/formalities?period_type=year&year=2026'
        self.assertEqual(len(self.clients[0].get(url).json()['items']),1)
        self.assertEqual(self.clients[1].get(url).json()['items'],[])
        self.assertEqual(self.quote(1).json()['totalCredits'],3)
        self.assertIsNone(self.quote(1).json()["items"][0]["ownedState"])
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
    def test_stale_quote_after_other_tab_uses_credit_has_precise_message(self):
        quote=self.quote().json()['quote']
        with self.factory.begin() as db:
            db.get(UserAccount,self.ids[0]).credit_balance=2
        result=self.submit(quote=quote)
        self.assertEqual(result.status_code,409)
        self.assertEqual(result.json()['detail'],"Tài khoản của bạn không đủ Credit để thực hiện lượt tra cứu này.")
        with self.factory() as db:
            self.assertEqual(db.scalar(select(func.count()).select_from(CollectionJob)),0)
            self.assertEqual(db.scalar(select(func.count()).select_from(PaidDataRequest)),0)
            self.assertEqual(db.get(UserAccount,self.ids[0]).credit_reserved,0)
    def test_source_wallet_stale_quote_preserves_other_hold_and_no_extra_events(self):
        from qd766.backend.credit_wallet import reserve,balance
        from qd766.backend.models import CreditWalletEvent
        self.source_wallet()
        quote=self.quote().json()['quote']
        now=datetime.now(timezone.utc)
        with self.factory.begin() as db:
            reserve(db,self.ids[0],600,request_key="other-tab",now=now)
        with self.factory() as db:
            before=balance(db,self.ids[0],now=now)
            events=db.scalar(select(func.count()).select_from(CreditWalletEvent))
        result=self.submit(quote=quote)
        self.assertEqual(result.status_code,409)
        self.assertEqual(result.json()['detail'],"Tài khoản của bạn không đủ Credit để thực hiện lượt tra cứu này.")
        with self.factory() as db:
            self.assertEqual(balance(db,self.ids[0],now=now),before)
            self.assertEqual(db.scalar(select(func.count()).select_from(CreditWalletEvent)),events)
            self.assertEqual(db.scalar(select(func.count()).select_from(CollectionJob)),0)
            self.assertEqual(db.scalar(select(func.count()).select_from(PaidDataRequest)),0)
    def test_notifications_persist_and_acknowledgement_is_account_scoped(self):
        first=self.submit().json()['items'][0]['id'];self.settle();self.submit(1)
        self.assertEqual(self.clients[0].get('/api/v1/me/formality-requests').json()['unreadNotifications'],1)
        self.clients[1].post('/api/v1/me/notifications/read',json={'requestIds':[first]},headers={'X-QD766-CSRF':'csrf-1'})
        self.assertEqual(self.clients[0].get('/api/v1/me/formality-requests').json()['unreadNotifications'],1)
        result=self.clients[0].post('/api/v1/me/notifications/read',json={'requestIds':[first]},headers={'X-QD766-CSRF':'csrf-0'})
        self.assertEqual(result.status_code,200)
        self.assertEqual(self.clients[0].get('/api/v1/me/formality-requests').json()['unreadNotifications'],0)
