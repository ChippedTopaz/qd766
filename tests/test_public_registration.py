from datetime import datetime, timedelta, timezone
from dataclasses import replace
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit
import unittest
from fastapi.testclient import TestClient
from sqlalchemy import select, func, event, delete
from qd766.backend.models import TrialRegistration, UserAccount, SubscriptionCycle, CreditWalletEvent, LoginSession
import test_shared_registration as shared_registration
from test_backend import ROOT_ID, CHILD_ID, TAY_NINH_ROOT_ID, TAY_NINH_CHILD_ID


class PublicRegistrationTests(unittest.TestCase):
    setUp=shared_registration.SharedRegistrationTests.setUp
    tearDown=shared_registration.SharedRegistrationTests.tearDown
    enable_default_invited_trial=shared_registration.SharedRegistrationTests.enable_default_invited_trial
    review=shared_registration.SharedRegistrationTests.review
    redeem=shared_registration.SharedRegistrationTests.redeem

    def join_public(self,sub='public-user'):
        client=TestClient(self.app,base_url='https://testserver',follow_redirects=False)
        self.addCleanup(client.close)
        start=client.get('/api/v1/auth/google/start?register=1')
        self.assertEqual(start.status_code,303,start.text)
        state=parse_qs(urlsplit(start.headers['location']).query)['state'][0]
        with patch('qd766.backend.auth.verify_google_identity',return_value={'sub':sub,'email':sub+'@example.com','name':'Google Name'}):
            result=client.get('/api/v1/auth/google/callback',params={'state':state,'code':'code'})
        self.assertEqual(result.headers['location'],'/')
        return client

    def payload(self,**extra):
        return dict(fullName='Nguyễn Văn A',birthDate='1990-05-17',gender='male',workplace='Văn phòng UBND',declarationAccepted=True,accessTier='agency',provinceId=ROOT_ID,unitId=CHILD_ID,**extra)

    def test_optional_workplace_and_required_declaration(self):
        client=self.join_public('optional-workplace');payload=self.payload();payload.pop('workplace')
        missing=dict(payload);missing.pop('declarationAccepted')
        self.assertEqual(self.submit(client,missing).status_code,422)
        self.assertEqual(self.submit(client,{**payload,'declarationAccepted':False}).status_code,422)
        self.assertEqual(self.submit(client,payload).status_code,200)

    def submit(self,client,payload):
        csrf=client.get('/api/v1/auth/registration').json()['csrfToken']
        return client.post('/api/v1/auth/registration/public',json=payload,headers={'X-QD766-CSRF':csrf})

    def test_agency_pending_then_one_month_from_approval(self):
        for tier in ('agency',):
            with self.subTest(tier=tier):
                client=self.join_public(tier)
                self.assertTrue(client.get('/api/v1/auth/registration').json()['publicRegistration'])
                self.assertEqual(client.get('/api/v1/dashboard').status_code,403)
                payload=self.payload();payload.update(accessTier=tier,unitId=None if tier=='province' else CHILD_ID)
                self.assertEqual(self.submit(client,payload).status_code,200)
                rows=self.client.get('/api/v1/admin/registrations').json();row=next(i for i in rows if i['email']==tier+'@example.com')
                self.assertEqual(row['birthDate'],'1990-05-17');self.assertEqual(row['accessTier'],tier)
                with self.app.state.session_factory.begin() as db:
                    item=db.scalar(select(TrialRegistration).where(TrialRegistration.id==__import__('uuid').UUID(row['id'])))
                    item.submitted_at=datetime.now(timezone.utc)-timedelta(days=10)
                    account_id=item.account_id
                    self.assertEqual(db.scalar(select(func.count()).select_from(SubscriptionCycle).where(SubscriptionCycle.account_id==account_id)),0)
                before=datetime.now(timezone.utc)
                approved=self.review([row['id']]);self.assertEqual(approved.status_code,200,approved.text)
                profile=client.get('/api/v1/auth/me').json()
                self.assertEqual(profile['accessTier'],tier);self.assertEqual(profile['name'],'Nguyễn Văn A');self.assertEqual(profile['credits'],100)
                self.assertEqual(client.get('/api/v1/dashboard?root_department_id='+TAY_NINH_ROOT_ID).status_code,403)
                self.assertEqual(self.review([row['id']]).json()['reviewed'],0)
                with self.app.state.session_factory() as db:
                    cycles=list(db.scalars(select(SubscriptionCycle).where(SubscriptionCycle.account_id==account_id)))
                    self.assertEqual(len(cycles),1)
                    self.assertGreaterEqual(cycles[0].starts_at.replace(tzinfo=timezone.utc),before)
                    self.assertEqual(cycles[0].ends_at.month,cycles[0].starts_at.month % 12 + 1)
                returning,_=self.redeem(sub=tier,email=tier+'@example.com');self.addCleanup(returning.close)
                self.assertEqual(returning.get('/api/v1/auth/me').json()['name'],'Nguyễn Văn A')

    def test_strict_fields_scope_csrf_and_no_credit_before_review(self):
        client=self.join_public();payload=self.payload()
        self.assertEqual(client.post('/api/v1/auth/registration/public',json=payload).status_code,403)
        for changes in ({'accessTier':'national'},{'unitId':TAY_NINH_CHILD_ID},{'unitId':ROOT_ID},
                        {'accessTier':'province','unitId':None},{'birthDate':'2999-01-01'},{'fullName':'  '},
                        {'gender':'unknown'},{'gender':'other'},{'workplace':'x'*241},{'role':'admin'}):
            bad={**payload,**changes};response=self.submit(client,bad)
            self.assertEqual(response.status_code,422,response.text)
        self.assertEqual(client.get('/api/v1/admin/registrations').status_code,403)
        self.assertEqual(self.submit(client,payload).status_code,200)
        self.assertEqual(self.submit(client,payload).status_code,409)
        with self.app.state.session_factory() as db:
            self.assertEqual(db.scalar(select(func.count()).select_from(CreditWalletEvent)),0)
        rows=self.client.get('/api/v1/admin/registrations').json()
        self.assertEqual(self.review([rows[0]['id']],'reject').status_code,200)
        self.assertEqual(client.get('/api/v1/dashboard').status_code,403)

    def test_explicit_intent_only_and_disabled_flag(self):
        client,result=self.redeem(sub='no-intent');self.addCleanup(client.close)
        self.assertEqual(result.headers['location'],'/?login=invite-required')
        self.app.state.settings=replace(self.app.state.settings,shared_registration_enabled=False)
        self.assertEqual(self.client.get('/api/v1/auth/google/start?register=1').status_code,503)

    def test_admin_assignment_validates_province_scope(self):
        client=self.join_public();self.submit(client,self.payload())
        row=self.client.get('/api/v1/admin/registrations').json()[0]
        path='/api/v1/admin/registrations/'+row['id']+'/assignment'
        data={'provinceId':ROOT_ID,'unitId':None,'accessTier':'province'}
        self.assertEqual(self.client.post(path,json=data).status_code,403)
        self.assertEqual(self.client.post(path,json=data,headers=self.headers).status_code,200)
        self.assertEqual(self.review([row['id']]).status_code,200)
        self.assertEqual(client.get('/api/v1/auth/me').json()['accessTier'],'province')

    def test_name_validation_rejects_probe_markup_and_controls_without_writes(self):
        client=self.join_public('name-validation')
        for name in ("'and 1=1", "Nguyễn OR 1=1 --", "A; DROP TABLE user_accounts", '<script>alert(1)</script>',
                     'Nguyễn\x00Văn A', 'Nguyễn\u200bVăn A', '12345', ' -- ', 'Nguyễn😀'):
            with self.subTest(name=name):
                self.assertEqual(self.submit(client,{**self.payload(),'fullName':name}).status_code,422)
        with self.app.state.session_factory() as db:
            registration=db.scalar(select(TrialRegistration))
            self.assertEqual(registration.state,'draft');self.assertIsNone(registration.full_name)
            self.assertEqual(db.scalar(select(func.count()).select_from(CreditWalletEvent)),0)
        self.assertEqual(self.submit(client,{**self.payload(),'fullName':"Nguyễn O'Connor"}).status_code,200)

    def test_name_allowlist_preserves_international_letters_and_apostrophes(self):
        import unicodedata
        from qd766.backend.trial_registration import PublicSelection
        for name in ('Đặng Thị Hồng',"D'Artagnan",'O’Connor','Jean-Luc','J. Nguyễn','李明',
                     unicodedata.normalize('NFD','Nguyễn Văn A')):
            with self.subTest(name=name):
                profile=PublicSelection.model_validate({**self.payload(),'fullName':name})
                self.assertEqual(profile.fullName,unicodedata.normalize('NFC',name))

    def test_profile_strings_are_bound_data_not_executable_sql(self):
        client=self.join_public('bound-data');statements=[]
        probe="Office ' OR 1=1; DROP TABLE user_accounts; --"
        def capture(connection,cursor,statement,parameters,context,executemany):
            statements.append((statement,parameters))
        event.listen(self.app.state.engine,'before_cursor_execute',capture)
        try:
            response=self.submit(client,{**self.payload(),'fullName':"D'Artagnan",'workplace':probe})
        finally:
            event.remove(self.app.state.engine,'before_cursor_execute',capture)
        self.assertEqual(response.status_code,200,response.text)
        self.assertTrue(statements)
        self.assertTrue(all(probe not in sql and "D'Artagnan" not in sql for sql,_ in statements))
        self.assertTrue(any(probe in str(parameters) for _,parameters in statements))
        with self.app.state.session_factory() as db:
            self.assertEqual(db.scalar(select(func.count()).select_from(UserAccount)),2)
            self.assertEqual(db.scalar(select(TrialRegistration)).workplace,probe)
            self.assertEqual(db.get(UserAccount,self.admin_id).role,'admin')
            self.assertEqual(db.scalar(select(func.count()).select_from(CreditWalletEvent)),0)

    def test_invalid_legacy_name_cannot_be_approved_but_can_be_rejected(self):
        client=self.join_public('legacy-name');self.submit(client,self.payload())
        row=self.client.get('/api/v1/admin/registrations').json()[0]
        with self.app.state.session_factory.begin() as db:
            item=db.scalar(select(TrialRegistration));item.full_name="'and 1=1"
        self.assertEqual(self.review([row['id']]).status_code,422)
        with self.app.state.session_factory() as db:
            item=db.scalar(select(TrialRegistration))
            self.assertEqual(item.state,'pending');self.assertFalse(db.get(UserAccount,item.account_id).trial_admitted)
            self.assertEqual(db.scalar(select(func.count()).select_from(CreditWalletEvent)),0)
        self.assertEqual(self.review([row['id']],'reject').status_code,200)

    def test_disabled_applicant_cannot_login_again_or_use_old_session(self):
        client=self.join_public('blocked-applicant');self.submit(client,self.payload())
        with self.app.state.session_factory.begin() as db:
            item=db.scalar(select(TrialRegistration));account=db.get(UserAccount,item.account_id)
            item.state='rejected';account.active=False
            db.execute(delete(LoginSession).where(LoginSession.account_id==account.id))
        self.assertEqual(client.get('/api/v1/auth/registration').status_code,401)
        self.assertEqual(client.get('/api/v1/dashboard').status_code,401)
        returning,result=self.redeem(sub='blocked-applicant',email='blocked-applicant@example.com')
        self.addCleanup(returning.close)
        self.assertEqual(result.headers['location'],'/?login=failed')
        self.assertEqual(returning.get('/api/v1/auth/registration').status_code,401)


if __name__=='__main__':unittest.main()
