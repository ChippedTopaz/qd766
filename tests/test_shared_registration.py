from dataclasses import replace
from datetime import datetime, timedelta, timezone
import uuid

from fastapi.testclient import TestClient
from sqlalchemy import select, func
import unittest
import test_trial_admin as fixtures
from test_backend import ROOT_ID, CHILD_ID, TAY_NINH_ROOT_ID, TAY_NINH_CHILD_ID
from qd766.backend.auth import digest
from qd766.backend.models import SharedTrialLink, TrialRegistration, SubscriptionCycle, CreditWalletEvent, UserAccount


class SharedRegistrationTests(unittest.TestCase):
    redeem=fixtures.TrialAdminTests.redeem
    invite=fixtures.TrialAdminTests.invite
    enable_default_invited_trial=fixtures.TrialAdminTests.enable_default_invited_trial
    tearDown=fixtures.TrialAdminTests.tearDown
    def setUp(self):
        fixtures.TrialAdminTests.setUp(self)
        self.enable_default_invited_trial()
        self.app.state.settings=replace(self.app.state.settings,shared_registration_enabled=True)

    def link(self, **options):
        response=self.client.post('/api/v1/admin/registration-links',json=options,headers=self.headers)
        self.assertEqual(response.status_code,200,response.text)
        return response.json()

    def join(self, token, sub='applicant'):
        client=TestClient(self.app,base_url='https://testserver',follow_redirects=False)
        self.addCleanup(client.close)
        response=client.post('/api/v1/auth/registration-link',json={'token':token})
        self.assertEqual(response.status_code,200,response.text)
        client,callback=self.redeem(sub=sub,email=sub+'@example.com',client=client)
        self.assertEqual(callback.headers['location'],'/')
        return client

    def submit(self, client, province=ROOT_ID, unit=CHILD_ID):
        status=client.get('/api/v1/auth/registration').json()
        return client.post('/api/v1/auth/registration',json={'provinceId':province,'unitId':unit},headers={'X-QD766-CSRF':status['csrfToken']})

    def review(self, ids, decision='approve'):
        return self.client.post('/api/v1/admin/registrations/review',json={'ids':ids,'decision':decision},headers=self.headers)

    def test_shared_pending_then_agency_approval_grants_once(self):
        link=self.link()
        with self.app.state.session_factory() as db:
            self.assertEqual(db.get(SharedTrialLink,uuid.UUID(link['id'])).token_hash,digest(link['token']))
        applicant=self.join(link['token'])
        self.assertEqual(applicant.get('/api/v1/auth/me').status_code,403)
        self.assertEqual(applicant.get('/api/v1/dashboard').status_code,403)
        self.assertEqual(self.submit(applicant).status_code,200)
        self.assertEqual(self.submit(applicant).status_code,409)
        with self.app.state.session_factory() as db:
            self.assertEqual(db.scalar(select(func.count()).select_from(SubscriptionCycle)),0)
            self.assertEqual(db.scalar(select(func.count()).select_from(CreditWalletEvent)),0)
        pending=self.client.get('/api/v1/admin/registrations').json()
        self.assertEqual(len(pending),1)
        result=self.review([pending[0]['id']]);self.assertEqual(result.status_code,200,result.text)
        profile=applicant.get('/api/v1/auth/me').json()
        self.assertEqual(profile['credits'],100)
        self.assertEqual(profile['accessTier'],'agency')
        self.assertEqual(profile['unitId'],CHILD_ID)
        self.assertTrue(profile['canCollect'])
        self.assertEqual(applicant.get('/api/v1/dashboard?root_department_id='+TAY_NINH_ROOT_ID).status_code,403)
        self.assertEqual(self.review([pending[0]['id']]).json()['reviewed'],0)
        with self.app.state.session_factory() as db:
            self.assertEqual(db.scalar(select(func.count()).select_from(SubscriptionCycle)),1)
            self.assertEqual(db.scalar(select(func.count()).select_from(CreditWalletEvent)),1)
        self.assertEqual(applicant.get('/api/v1/auth/registration').json()['state'],'approved')
        returning,_=self.redeem(sub='applicant',email='applicant@example.com')
        self.addCleanup(returning.close)
        self.assertEqual(returning.get('/api/v1/auth/me').json()['credits'],100)

    def test_scope_and_csrf_cannot_be_bypassed(self):
        link=self.link();client=self.join(link['token'])
        status=client.get('/api/v1/auth/registration').json()
        path='/api/v1/auth/registration'
        self.assertEqual(client.post(path,json={'provinceId':ROOT_ID,'unitId':CHILD_ID}).status_code,403)
        for payload in ({'provinceId':ROOT_ID,'unitId':TAY_NINH_CHILD_ID},{'provinceId':ROOT_ID,'unitId':ROOT_ID},
                        {'provinceId':ROOT_ID,'unitId':CHILD_ID,'accessTier':'national'},
                        {'provinceId':"' OR 1=1 --",'unitId':CHILD_ID}):
            self.assertEqual(client.post(path,json=payload,headers={'X-QD766-CSRF':status['csrfToken']}).status_code,422)
        self.assertEqual(client.get('/api/v1/admin/registrations').status_code,403)
        with self.app.state.session_factory() as db:
            self.assertEqual(db.get(SharedTrialLink,uuid.UUID(link['id'])).registered_count,0)
        anonymous=TestClient(self.app,base_url='https://testserver');self.addCleanup(anonymous.close)
        self.assertEqual(anonymous.get('/api/v1/auth/registration/directory').status_code,401)

    def test_capacity_revoke_and_expiry(self):
        link=self.link(maxRegistrations=1)
        a=self.join(link['token'],'a');b=self.join(link['token'],'b')
        self.assertEqual(self.submit(a).status_code,200)
        self.assertEqual(self.submit(b).status_code,403)
        self.assertEqual(b.post('/api/v1/auth/registration-link',json={'token':link['token']}).status_code,403)
        another=self.link();c=self.join(another['token'],'c')
        self.client.post('/api/v1/admin/registration-links/'+another['id']+'/revoke',json={},headers=self.headers)
        self.assertEqual(self.submit(c).status_code,403)
        expired=self.link();d=self.join(expired['token'],'d')
        with self.app.state.session_factory.begin() as db:
            db.get(SharedTrialLink,uuid.UUID(expired['id'])).expires_at=datetime.now(timezone.utc)-timedelta(days=1)
        self.assertEqual(self.submit(d).status_code,403)
        returning,result=self.redeem(sub='a',email='a@example.com');self.addCleanup(returning.close)
        self.assertEqual(result.headers['location'],'/')
        self.assertEqual(returning.get('/api/v1/auth/registration').json()['state'],'pending')

    def test_batch_edit_and_reject(self):
        link=self.link();a=self.join(link['token'],'a');b=self.join(link['token'],'b')
        self.submit(a);self.submit(b)
        rows=self.client.get('/api/v1/admin/registrations').json();aid=next(r['id'] for r in rows if r['email']=='a@example.com')
        changed=self.client.post('/api/v1/admin/registrations/'+aid+'/assignment',json={'provinceId':TAY_NINH_ROOT_ID,'unitId':TAY_NINH_CHILD_ID},headers=self.headers)
        self.assertEqual(changed.status_code,200,changed.text)
        self.assertEqual(self.review([aid]).status_code,200)
        self.assertEqual(a.get('/api/v1/auth/me').json()['unitId'],TAY_NINH_CHILD_ID)
        bid=next(r['id'] for r in rows if r['email']=='b@example.com')
        self.assertEqual(self.review([bid],'reject').status_code,200)
        self.assertEqual(b.get('/api/v1/auth/registration').json()['state'],'rejected')
        self.assertEqual(b.get('/api/v1/dashboard').status_code,403)

    def test_batch_rollback_missing_record_and_direct_invites_unchanged(self):
        link=self.link();a=self.join(link['token']);self.submit(a)
        row=self.client.get('/api/v1/admin/registrations').json()[0]
        self.assertEqual(self.review([row['id'],str(uuid.uuid4())]).status_code,404)
        self.assertEqual(a.get('/api/v1/auth/registration').json()['state'],'pending')
        invite=self.invite(accessTier='agency',unitId=CHILD_ID)
        direct,_=self.redeem(invite['token'],sub='direct');self.addCleanup(direct.close)
        self.assertEqual(direct.get('/api/v1/auth/me').json()['credits'],100)

    def test_feature_disabled_keeps_old_schema_compatible(self):
        self.app.state.settings=replace(self.app.state.settings,shared_registration_enabled=False)
        self.assertEqual(self.client.get('/api/v1/admin/registrations').status_code,503)
        self.assertEqual(self.client.post('/api/v1/auth/registration-link',json={'token':'x'*43}).status_code,503)

    def test_expired_link_between_acceptance_and_oauth_denies_new_account(self):
        link=self.link()
        client=TestClient(self.app,base_url='https://testserver',follow_redirects=False);self.addCleanup(client.close)
        self.assertEqual(client.post('/api/v1/auth/registration-link',json={'token':link['token']}).status_code,200)
        with self.app.state.session_factory.begin() as db:
            db.get(SharedTrialLink,uuid.UUID(link['id'])).expires_at=datetime.now(timezone.utc)-timedelta(seconds=1)
        _,response=self.redeem(sub='expired',email='expired@example.com',client=client)
        self.assertEqual(response.headers['location'],'/?login=invite-required')
        self.assertEqual(client.get('/api/v1/auth/registration').status_code,401)

    def test_shared_link_admin_csrf_and_no_tier_payload(self):
        path='/api/v1/admin/registration-links'
        self.assertEqual(self.client.post(path,json={}).status_code,403)
        self.assertEqual(self.client.post(path,json={'accessTier':'province'},headers=self.headers).status_code,422)
        link=self.link();client=self.join(link['token'])
        self.assertEqual(client.post(path,json={},headers={'X-QD766-CSRF':client.get('/api/v1/auth/registration').json()['csrfToken']}).status_code,403)


if __name__=='__main__':
    import unittest
    unittest.main()
