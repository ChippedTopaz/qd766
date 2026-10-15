"""Public signup replaces new invite issuance, not approval or existing identities."""
import uuid
import unittest
from sqlalchemy import select,func
from qd766.backend.models import TrialInvitation,SharedTrialLink,UserAccount,SubscriptionCycle,CreditWalletEvent,AdminAudit
from test_backend import ROOT_ID,TAY_NINH_ROOT_ID,CHILD_ID
import test_public_registration as public


class InvitationRetirementTests(unittest.TestCase):
    setUp=public.PublicRegistrationTests.setUp
    tearDown=public.PublicRegistrationTests.tearDown
    enable_default_invited_trial=public.PublicRegistrationTests.enable_default_invited_trial
    join_public=public.PublicRegistrationTests.join_public
    payload=public.PublicRegistrationTests.payload
    submit=public.PublicRegistrationTests.submit
    review=public.PublicRegistrationTests.review
    redeem=public.PublicRegistrationTests.redeem

    def test_new_invites_disabled_with_csrf_and_no_writes(self):
        cases=[('/api/v1/admin/invitations',{'provinceId':ROOT_ID}),('/api/v1/admin/registration-links',{})]
        for path,payload in cases:
            self.assertEqual(self.client.post(path,json=payload).status_code,403)
            r=self.client.post(path,json=payload,headers=self.headers)
            self.assertEqual(r.status_code,410,r.text);self.assertIn('đăng ký',r.json()['detail'])
        with self.app.state.session_factory() as db:
            for model in (TrialInvitation,SharedTrialLink,SubscriptionCycle,CreditWalletEvent,AdminAudit):
                self.assertEqual(db.scalar(select(func.count()).select_from(model)),0)
        self.assertEqual(self.client.get('/api/v1/admin/invitations').json(),[])
        self.assertEqual(self.client.get('/api/v1/admin/registration-links').json(),[])

    def test_public_review_then_upgrade_keeps_credit_subscription_and_role(self):
        client=self.join_public('scope-upgrade');self.assertEqual(self.submit(client,self.payload()).status_code,200)
        row=self.client.get('/api/v1/admin/registrations').json()[0]
        self.assertEqual(self.review([row['id']]).status_code,200)
        profile=client.get('/api/v1/auth/me').json();identifier=uuid.UUID(profile['id'])
        self.assertEqual(profile['accessTier'],'agency');self.assertEqual(profile['credits'],100)
        self.assertEqual(client.get('/api/v1/dashboard?root_department_id='+TAY_NINH_ROOT_ID).status_code,403)
        with self.app.state.session_factory() as db:
            cycle=db.scalar(select(SubscriptionCycle).where(SubscriptionCycle.account_id==identifier))
            original=(cycle.id,cycle.starts_at,cycle.ends_at,cycle.included_credit)
            events=db.scalar(select(func.count()).select_from(CreditWalletEvent).where(CreditWalletEvent.account_id==identifier))
            invitations=db.scalar(select(func.count()).select_from(TrialInvitation))
        path='/api/v1/admin/accounts/'+str(identifier)
        for scope in ('province','national','agency'):
            body={'provinceId':ROOT_ID,'accessTier':scope,'unitId':CHILD_ID if scope=='agency' else None,'active':True}
            self.assertEqual(self.client.post(path,json=body).status_code,403)
            self.assertEqual(self.client.post(path,json=body,headers=self.headers).status_code,200)
            self.assertEqual(client.get('/api/v1/auth/me').status_code,401,'Scope updates revoke old sessions')
            # Simulated Google only; prove relogin retains approved admission.
            client,_=self.redeem(sub='scope-upgrade',email='scope-upgrade@example.com',client=client)
            changed=client.get('/api/v1/auth/me').json()
            self.assertEqual(changed['accessTier'],scope);self.assertEqual(changed['role'],'user');self.assertEqual(changed['credits'],100)
            self.assertEqual(client.get('/api/v1/admin/accounts').status_code,403)
            self.assertEqual(client.get('/api/v1/dashboard?root_department_id='+TAY_NINH_ROOT_ID).status_code,200 if scope=='national' else 403)
            with self.app.state.session_factory() as db:
                cycle=db.scalar(select(SubscriptionCycle).where(SubscriptionCycle.account_id==identifier))
                self.assertEqual((cycle.id,cycle.starts_at,cycle.ends_at,cycle.included_credit),original)
                self.assertEqual(db.scalar(select(func.count()).select_from(CreditWalletEvent).where(CreditWalletEvent.account_id==identifier)),events)
                self.assertEqual(db.scalar(select(func.count()).select_from(TrialInvitation)),invitations)
                self.assertEqual(db.scalar(select(func.count()).select_from(SubscriptionCycle).where(SubscriptionCycle.account_id==identifier)),1)
        self.assertEqual(self.review([row['id']]).json()['reviewed'],0)

    def test_scope_edit_does_not_admit_an_unapproved_account(self):
        client=self.join_public('not-reviewed');self.submit(client,self.payload())
        row=self.client.get('/api/v1/admin/registrations').json()[0]
        with self.app.state.session_factory() as db:
            account=db.scalar(select(UserAccount).where(UserAccount.email=='not-reviewed@example.com'));identifier=account.id
        r=self.client.post('/api/v1/admin/accounts/'+str(identifier),json={'provinceId':ROOT_ID,'accessTier':'province','active':True},headers=self.headers)
        self.assertEqual(r.status_code,200)
        with self.app.state.session_factory() as db:
            self.assertFalse(db.get(UserAccount,identifier).trial_admitted)
            self.assertEqual(db.scalar(select(func.count()).select_from(SubscriptionCycle)),0)
        self.assertEqual(self.client.get('/api/v1/admin/registrations').json()[0]['id'],row['id'])


if __name__=='__main__':unittest.main()
