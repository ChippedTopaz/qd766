"""Whole invite-to-library journey; fake Google identity and simulated data only."""
import sys
import unittest
import uuid
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"src"))
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from qd766.backend.app import create_app
from qd766.backend.auth import digest
from qd766.backend.importer import store_normalized_snapshot
from qd766.backend.config import Settings
from qd766.backend.local_credit_trial import ROOT, identifier, mock_catalog, mock_snapshot
from qd766.backend.models import Base, CollectionJob, CreditWalletEvent, LoginSession, SubscriptionCycle, UserAccount
from qd766.backend.worker import run_one_job


class TrialJourneyTests(unittest.TestCase):
    database_url="sqlite+pysqlite://"
    origin="https://testserver"
    real_wallet_runtime=False

    def setUp(self):
        self.app=create_app(Settings(database_url=self.database_url,public_read_only=True,
            require_login=True,invite_required=True,paid_requests_enabled=True,
            trial_credits_enabled=True,trial_credit_management=True,formality_credit_cost=5,
            google_client_id="test",google_client_secret="fake-test-secret",
            google_redirect_uri="https://testserver/api/v1/auth/google/callback"))
        # Explicit isolated test injection; production config cannot enable this.
        if not self.real_wallet_runtime:
            self.app.state.settings=replace(self.app.state.settings,source_wallet_trial=True)
        self.factory=self.app.state.session_factory
        if not self.real_wallet_runtime:
            self.factory.configure(info={"source_wallet_enabled":True,"default_collection_access":True})
        self.app.state.province_catalog_client=SimpleNamespace(load=lambda *a,**k:mock_catalog())
        Base.metadata.create_all(self.app.state.engine)
        with self.factory.begin() as db:
            store_normalized_snapshot(db,mock_snapshot())
            admin=UserAccount(external_subject="google:journey-admin",display_name="Journey admin",
                role="admin",trial_admitted=True,root_department_id=ROOT)
            db.add(admin);db.flush()
            db.add(LoginSession(token_hash=digest("journey-owner-token"),account_id=admin.id,
                csrf_token="journey-owner-csrf",expires_at=datetime.now(timezone.utc)+timedelta(hours=1)))
        self.admin=TestClient(self.app,base_url=self.origin,follow_redirects=False)
        self.admin.cookies.set("qd766_session","journey-owner-token")
        self.clients=[self.admin]

    def tearDown(self):
        for client in self.clients:client.close()
        self.app.state.engine.dispose()

    def login(self,client,subject):
        start=client.get("/api/v1/auth/google/start")
        state=parse_qs(urlsplit(start.headers["location"]).query)["state"][0]
        with patch("qd766.backend.auth.verify_google_identity",return_value={
                "sub":subject,"email":subject+"@example.test","name":subject}):
            response=client.get("/api/v1/auth/google/callback",params={"state":state,"code":"fake-code"})
        self.assertEqual(response.headers["location"],"/")
        return client.get("/api/v1/auth/me").json()

    def invite(self,subject,agency=False):
        body={"provinceId":str(ROOT),"email":subject+"@example.test",
              "accessTier":"agency" if agency else "province"}
        if agency:body["unitId"]=str(identifier("department:commune"))
        invite=self.admin.post("/api/v1/admin/invitations",json=body,
            headers={"X-QD766-CSRF":"journey-owner-csrf"})
        self.assertEqual(invite.status_code,200)
        client=TestClient(self.app,base_url=self.origin,follow_redirects=False)
        self.clients.append(client)
        self.assertEqual(client.post("/api/v1/auth/invite",json={"token":invite.json()["token"]}).status_code,200)
        profile=self.login(client,subject)
        self.assertEqual(profile["credits"],100)
        self.assertTrue(profile["canCollect"])
        return client,profile

    def quote(self,client,profile,month=None):
        return client.post("/api/v1/me/collection-quote",json={"periodType":"year" if month is None else "month",
            "year":2026,"periodValue":month,"formalityIds":[str(identifier("formality:1"))]},
            headers={"X-QD766-CSRF":profile["csrfToken"]})

    def submit(self,client,profile,month=None):
        quote=self.quote(client,profile,month)
        self.assertEqual(quote.status_code,200)
        return client.post("/api/v1/me/formality-requests",json={"quote":quote.json()["quote"],"token":str(uuid.uuid4())},
            headers={"X-QD766-CSRF":profile["csrfToken"]})

    def wallet(self,client):return client.get("/api/v1/me/credits").json()

    def test_complete_trial_journey(self):
        a,pa=self.invite("journey-a")
        b,pb=self.invite("journey-b",agency=True)
        for client,profile in ((a,pa),(b,pb)):
            self.assertEqual(self.submit(client,profile).status_code,202)
            self.assertEqual((self.wallet(client)["availableCredits"],self.wallet(client)["reservedCredits"]),(95,5))
        with self.factory() as db:
            self.assertEqual(db.scalar(select(func.count()).select_from(CollectionJob)),1)
        outcome=run_one_job(self.factory,lambda job,request:mock_snapshot(request),worker_id="journey-mock")
        self.assertEqual(outcome.state,"succeeded")
        for client,profile in ((a,pa),(b,pb)):
            self.assertEqual((self.wallet(client)["availableCredits"],self.wallet(client)["reservedCredits"]),(95,0))
            self.assertEqual(self.quote(client,profile).json()["totalCredits"],0)
            self.assertEqual(self.submit(client,profile).json()["availableCredits"],95)
            self.assertEqual(len(client.get("/api/v1/me/formalities?period_type=year&year=2026").json()["items"]),1)
            detail=client.get(f"/api/v1/dashboard/selection?scope=formality&period_type=year&year=2026&formality_id={identifier('formality:1')}")
            self.assertEqual(detail.status_code,200)
            self.assertEqual(len(detail.json()["snapshot"]["datasets"]),6)
        agency=b.get("/api/v1/dashboard").json()
        self.assertEqual([u["departmentId"] for u in agency["units"]],[str(identifier("department:commune"))])
        self.assertEqual(b.get("/api/v1/admin/accounts").status_code,403)
        # Shared cache is not free access for a third account.
        c,pc=self.invite("journey-c")
        self.assertEqual(c.get("/api/v1/me/formalities?period_type=year&year=2026").json()["items"],[])
        self.assertEqual(self.submit(c,pc).json()["items"][0]["state"],"ready")
        self.assertEqual(self.wallet(c)["availableCredits"],95)
        # Two pending requests, blocked third, failure refund and released slot.
        self.assertEqual(self.submit(a,pa,8).status_code,202)
        self.assertEqual(self.submit(a,pa,9).status_code,202)
        self.assertEqual(self.submit(a,pa,7).status_code,409)
        self.assertEqual((self.wallet(a)["availableCredits"],self.wallet(a)["reservedCredits"]),(85,10))
        def failure(job,request):raise RuntimeError("simulated source failure")
        outcome=run_one_job(self.factory,failure,worker_id="journey-mock",max_attempts=1)
        self.assertEqual(outcome.state,"failed")
        self.assertEqual((self.wallet(a)["availableCredits"],self.wallet(a)["reservedCredits"]),(90,5))
        self.assertEqual(self.submit(a,pa,7).status_code,202)
        before=self.wallet(a)["availableCredits"]
        pa=self.login(a,"journey-a")
        self.assertEqual(pa["credits"],before)
        with self.factory() as db:
            aid=uuid.UUID(pa["id"])
            self.assertEqual(db.scalar(select(func.count()).select_from(SubscriptionCycle).where(SubscriptionCycle.account_id==aid)),1)
            self.assertEqual(db.scalar(select(func.count()).select_from(CreditWalletEvent).where(
                CreditWalletEvent.account_id==aid,CreditWalletEvent.kind=="grant")),1)
        # Admin locks account and existing session immediately loses access.
        locked=self.admin.post("/api/v1/admin/accounts/"+pa["id"],json={"provinceId":str(ROOT),"active":False},
            headers={"X-QD766-CSRF":"journey-owner-csrf"})
        self.assertEqual(locked.status_code,200)
        self.assertEqual(a.get("/api/v1/auth/me").status_code,401)
        # Locking does not strand held Credit: mock worker refunds remaining jobs.
        while run_one_job(self.factory,failure,worker_id="journey-mock",max_attempts=1) is not None:
            pass
        from qd766.backend.credit_wallet import balance
        with self.factory() as db:
            self.assertEqual(balance(db,aid,now=datetime.now(timezone.utc))["reserved"],0)
            self.assertEqual(balance(db,aid,now=datetime.now(timezone.utc))["available"],95)


if __name__=="__main__":unittest.main()
