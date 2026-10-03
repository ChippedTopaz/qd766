import sys
import unittest
import uuid
from pathlib import Path
from sqlalchemy import func, select
from fastapi.testclient import TestClient

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"src"))
from qd766.backend.app import create_app
from qd766.backend.config import Settings
from qd766.backend.local_credit_trial import create_local_credit_trial, identifier, mock_catalog
from qd766.backend.models import AccountCollectionPermission, Base, CollectionJob, CreditLedgerEntry, PaidDataRequest, UserAccount


class LocalCreditTrialTests(unittest.TestCase):
    def setUp(self):
        self.app=create_local_credit_trial("sqlite+pysqlite://")
        self.clients={key:TestClient(self.app,base_url="http://127.0.0.1:8770",client=("127.0.0.1",43210),follow_redirects=False)
                      for key in ("admin","a","b","agency","no-permission")}
        for key,c in self.clients.items():
            self.assertEqual(c.post("/api/v1/local-trial/login",json={"account":key}).status_code,200)
        self.formality=mock_catalog().formalities[0].id
        self.selection={"periodType":"year","year":2026,"periodValue":None,"formalityIds":[self.formality]}

    def tearDown(self):
        for client in self.clients.values():client.close()
        self.app.state.engine.dispose()

    def headers(self,key):
        return {"X-QD766-CSRF":self.clients[key].get("/api/v1/auth/me").json()["csrfToken"]}

    def quote(self,key="a",selection=None):
        return self.clients[key].post("/api/v1/me/collection-quote",json=selection or self.selection,headers=self.headers(key))

    def submit(self,key="a",quote=None,token=None):
        return self.clients[key].post("/api/v1/me/formality-requests",json={"quote":quote or self.quote(key).json()["quote"],
            "token":token or str(uuid.uuid4())},headers=self.headers(key))

    def outcome(self,action):
        jobs=self.clients["admin"].get("/api/v1/local-trial/jobs").json()
        job=next((j for j in jobs if j["state"] in {"queued","running"}),None)
        return self.clients["admin"].post("/api/v1/local-trial/outcome",json={"action":action,
            "jobId":job["id"] if job and not action.startswith("circuit-") else None},headers=self.headers("admin"))

    def grant(self,key="a",amount=5,allowed=True,operation=None):
        return self.clients["admin"].post(f'/api/v1/admin/accounts/{identifier("account:"+key)}/trial-credit',
            json={"operationId":operation or str(uuid.uuid4()),"amount":amount,"canCollect":allowed,"reason":"Kiểm thử local"},
            headers=self.headers("admin"))

    def test_no_production_database_or_remote_host_or_cross_origin(self):
        with self.assertRaises(ValueError):create_local_credit_trial("postgresql+psycopg://localhost/qd766")
        c=TestClient(self.app,base_url="http://evil.example",client=("127.0.0.1",123))
        self.assertEqual(c.post("/api/v1/local-trial/login",json={"account":"admin"}).status_code,403);c.close()
        c=TestClient(self.app,base_url="http://127.0.0.1:8770",client=("192.168.1.2",123))
        self.assertEqual(c.get("/api/v1/local-trial/accounts").status_code,403);c.close()
        self.assertEqual(self.clients["a"].post("/api/v1/local-trial/login",json={"account":"admin"},
            headers={"Origin":"https://evil.example"}).status_code,403)
        self.assertEqual(self.clients["a"].get("/api/v1/auth/google/start").status_code,403)

    def test_permission_separate_from_credit_and_plan(self):
        self.assertEqual(self.clients["no-permission"].get("/api/v1/auth/me").json()["credits"],30)
        self.assertFalse(self.clients["no-permission"].get("/api/v1/auth/me").json()["canCollect"])
        self.assertEqual(self.quote("no-permission").status_code,403)
        self.assertEqual(self.grant("no-permission",0).status_code,200)
        self.assertEqual(self.quote("no-permission").status_code,200)
        with self.app.state.session_factory() as db:
            self.assertEqual(db.get(UserAccount,identifier("account:no-permission")).plan,"free")

    def test_selection_and_quote_do_not_create_jobs_or_charge(self):
        data=self.clients["a"].get("/api/v1/dashboard").json()
        self.assertEqual(len(next(iter(data["snapshots"].values()))["datasets"]),6)
        self.assertEqual(self.quote().json()["totalCredits"],3)
        with self.app.state.session_factory() as db:
            self.assertEqual(db.scalar(select(func.count()).select_from(CollectionJob)),0)
            self.assertEqual(db.scalar(select(func.count()).select_from(PaidDataRequest)),0)
            self.assertEqual(db.get(UserAccount,identifier("account:a")).credit_balance,30)

    def test_fresh_confirmation_retries_terminal_job_and_shares_successor(self):
        for outcome in ("failure", "cancel"):
            with self.subTest(outcome=outcome):
                selection=dict(self.selection, formalityIds=[mock_catalog().formalities[1 if outcome=="failure" else 2].id])
                token=str(uuid.uuid4())
                quote=self.quote(selection=selection).json()["quote"]
                first=self.submit(quote=quote,token=token).json()["items"][0]
                self.assertEqual(self.outcome(outcome).status_code,200)
                # Replaying an old confirmation must never create a new attempt.
                replay=self.submit(quote=quote,token=token).json()["items"][0]
                self.assertEqual(replay["id"],first["id"])
                self.assertEqual(replay["state"],"refunded")
                # Merely reading a new quote also does not retry a job.
                new_quote=self.quote(selection=selection).json()["quote"]
                jobs_before=self.clients["admin"].get("/api/v1/local-trial/jobs").json()
                self.assertFalse(any(j["state"]=="queued" for j in jobs_before))
                retried=self.submit(quote=new_quote).json()["items"][0]
                self.assertEqual(retried["state"],"waiting")
                self.assertNotEqual(retried["id"],first["id"])
                self.assertEqual(self.submit("b",quote=self.quote("b",selection).json()["quote"]).status_code,202)
                jobs=self.clients["admin"].get("/api/v1/local-trial/jobs").json()
                self.assertEqual(sum(j["state"]=="queued" for j in jobs),1)
                self.assertEqual(len(jobs),len(jobs_before)+1)
                self.assertEqual(self.outcome("success").status_code,200)
                for key in ("a","b"):
                    rows=self.clients[key].get("/api/v1/me/formality-requests").json()["items"]
                    self.assertTrue(any(r["formalityId"]==selection["formalityIds"][0] and r["state"]=="ready" for r in rows))
                history=self.clients["a"].get("/api/v1/me/formality-requests").json()
                self.assertEqual(next(r for r in history["items"] if r["id"]==first["id"])["state"],"refunded")
        for key in ("a","b"):
            me=self.clients[key].get("/api/v1/auth/me").json()
            self.assertEqual((me["credits"],me["reservedCredits"]),(24,0))

    def test_queued_dedup_success_notification_and_personal_library(self):
        self.assertEqual(self.submit().status_code,202)
        self.assertEqual(self.submit("b").status_code,202)
        with self.app.state.session_factory() as db:
            self.assertEqual(db.scalar(select(func.count()).select_from(CollectionJob)),1)
            for key in ("a","b"):
                a=db.get(UserAccount,identifier("account:"+key));self.assertEqual((a.credit_balance,a.credit_reserved),(27,3))
        self.assertEqual(self.outcome("success").status_code,200)
        for key in ("a","b"):
            history=self.clients[key].get("/api/v1/me/formality-requests").json()
            self.assertEqual((history["availableCredits"],history["reservedCredits"],history["unreadNotifications"]),(27,0,1))
            library=self.clients[key].get("/api/v1/me/formalities?period_type=year&year=2026").json()["items"]
            self.assertEqual(library[0]["id"],self.formality)
            view=self.clients[key].get(f"/api/v1/dashboard/selection?scope=formality&period_type=year&year=2026&formality_id={self.formality}")
            self.assertEqual(view.status_code,200);self.assertEqual(len(view.json()["snapshot"]["datasets"]),6)
        self.assertEqual(self.quote().json()["totalCredits"],0)
        self.assertEqual(self.submit().status_code,202)
        with self.app.state.session_factory() as db:
            self.assertEqual(db.scalar(select(func.count()).select_from(CreditLedgerEntry).where(CreditLedgerEntry.entry_type=="charge")),2)

    def test_shared_ready_data_charged_to_new_user_without_new_job(self):
        self.submit();self.outcome("success")
        self.assertEqual(self.clients["b"].get("/api/v1/me/formalities?period_type=year&year=2026").json()["items"],[])
        self.assertEqual(self.quote("b").json()["totalCredits"],3)
        result=self.submit("b").json()
        self.assertEqual(result["items"][0]["state"],"ready")
        self.assertEqual(result["availableCredits"],27)
        with self.app.state.session_factory() as db:
            self.assertEqual(db.scalar(select(func.count()).select_from(CollectionJob)),1)

    def test_failure_refund(self):
        self.submit();self.assertEqual(self.outcome("failure").status_code,200)
        history=self.clients["a"].get("/api/v1/me/formality-requests").json()
        self.assertEqual((history["availableCredits"],history["reservedCredits"]),(30,0))
        self.assertEqual(history["items"][0]["state"],"refunded")

    def test_cancel_refund(self):
        self.submit();self.assertEqual(self.outcome("cancel").status_code,200)
        history=self.clients["a"].get("/api/v1/me/formality-requests").json()
        self.assertEqual((history["availableCredits"],history["reservedCredits"]),(30,0))

    def test_circuit_refunds_shared_holds_and_blocks_new_charge(self):
        self.submit();self.submit("b");self.assertEqual(self.outcome("circuit-open").status_code,200)
        for key in ("a","b"):
            history=self.clients[key].get("/api/v1/me/formality-requests").json()
            self.assertEqual((history["availableCredits"],history["reservedCredits"]),(30,0))
        self.assertEqual(self.submit().status_code,409)

    def test_submit_token_replay_and_topup_replay_are_idempotent(self):
        quote=self.quote().json()["quote"];token=str(uuid.uuid4())
        self.submit(quote=quote,token=token);self.submit(quote=quote,token=token)
        operation=str(uuid.uuid4())
        self.assertEqual(self.grant(operation=operation).status_code,200)
        self.assertTrue(self.grant(operation=operation).json()["replayed"])
        self.assertEqual(self.grant(amount=6,operation=operation).status_code,409)
        with self.app.state.session_factory() as db:
            a=db.get(UserAccount,identifier("account:a"));self.assertEqual((a.credit_balance,a.credit_reserved),(32,3))
            self.assertEqual(db.scalar(select(func.count()).select_from(PaidDataRequest)),1)

    def test_ordinary_user_cannot_grant_or_simulate_worker(self):
        self.assertEqual(self.clients["a"].get("/api/v1/local-trial/jobs").status_code,403)
        self.assertEqual(self.clients["a"].post("/api/v1/local-trial/outcome",json={"action":"circuit-open"},headers=self.headers("a")).status_code,403)
        self.assertEqual(self.clients["a"].post(f'/api/v1/admin/accounts/{identifier("account:a")}/trial-credit',
            json={"operationId":str(uuid.uuid4()),"amount":100,"canCollect":True,"reason":"Self topup"},headers=self.headers("a")).status_code,403)

    def test_revoke_between_quote_and_submit(self):
        quote=self.quote().json()["quote"]
        self.assertEqual(self.grant(amount=0,allowed=False).status_code,200)
        self.assertEqual(self.submit(quote=quote).status_code,403)
        with self.app.state.session_factory() as db:
            self.assertEqual(db.scalar(select(func.count()).select_from(CollectionJob)),0)

    def test_insufficient_credit_batch_is_atomic_and_does_not_add_jobs(self):
        for month in range(1,9):
            selection=dict(self.selection,periodType="month",periodValue=month)
            self.assertEqual(self.submit(quote=self.quote(selection=selection).json()["quote"]).status_code,202)
        selection=dict(self.selection,formalityIds=[item.id for item in mock_catalog().formalities])
        quote=self.quote(selection=selection).json()
        self.assertEqual((quote["availableCredits"],quote["totalCredits"]),(6,9))
        self.assertEqual(self.submit(quote=quote["quote"]).status_code,409)
        me=self.clients["a"].get("/api/v1/auth/me").json()
        self.assertEqual((me["credits"],me["reservedCredits"]),(6,24))
        with self.app.state.session_factory() as db:
            self.assertEqual(db.scalar(select(func.count()).select_from(CollectionJob)),8)
            self.assertEqual(db.scalar(select(func.count()).select_from(PaidDataRequest)),8)
            self.assertEqual(db.scalar(select(func.count()).select_from(CreditLedgerEntry).where(CreditLedgerEntry.entry_type=="reserve")),8)

    def test_revoke_new_collection_permission_does_not_drop_pending_request(self):
        self.assertEqual(self.submit().status_code,202)
        self.assertEqual(self.grant(amount=0,allowed=False).status_code,200)
        self.assertEqual(self.quote().status_code,403)
        self.assertEqual(self.outcome("success").status_code,200)
        me=self.clients["a"].get("/api/v1/auth/me").json()
        self.assertEqual((me["credits"],me["reservedCredits"]),(27,0))
        view=self.clients["a"].get(f"/api/v1/dashboard/selection?scope=formality&period_type=year&year=2026&formality_id={self.formality}")
        self.assertEqual(view.status_code,200)

    def test_agency_paid_data_stays_scoped_and_shared_cache_is_not_redacted(self):
        path=f"/api/v1/dashboard/selection?scope=formality&period_type=year&year=2026&formality_id={self.formality}"
        self.assertEqual(self.clients["agency"].get(path).status_code,403)
        self.assertEqual(self.submit("agency").status_code,202)
        self.assertEqual(self.outcome("success").status_code,200)
        snapshot=self.clients["agency"].get(path).json()["snapshot"]
        self.assertIsNone(snapshot["provinceAggregatedScore"])
        for dataset in snapshot["datasets"]:
            self.assertIsNone(dataset["root"]["apiScore"])
            self.assertEqual(dataset["root"]["metrics"],[])
            for child in dataset["children"]:
                if child["departmentId"]==str(identifier("department:commune")):
                    self.assertTrue(child["metrics"])
                else:
                    self.assertEqual(child["metrics"],[])
                    self.assertEqual(child["parameters"],{})
        # Other accounts cannot open the shared result before buying access.
        self.assertEqual(self.clients["b"].get(path).status_code,403)
        self.assertEqual(self.submit("b").status_code,202)
        province_snapshot=self.clients["b"].get(path).json()["snapshot"]
        self.assertEqual(province_snapshot["provinceAggregatedScore"],70)
        self.assertTrue(province_snapshot["datasets"][0]["root"]["metrics"])

    def test_revoked_permission_keeps_previously_purchased_library(self):
        self.submit();self.outcome("success");self.grant(amount=0,allowed=False)
        self.assertEqual(self.quote().status_code,403)
        self.assertEqual(len(self.clients["a"].get("/api/v1/me/formalities?period_type=year&year=2026").json()["items"]),1)

    def test_ledger_read_and_csrf_on_grant(self):
        account=str(identifier("account:a"))
        self.assertEqual(self.clients["admin"].post(f"/api/v1/admin/accounts/{account}/trial-credit",
            json={"operationId":str(uuid.uuid4()),"amount":10,"canCollect":True,"reason":"Test"}).status_code,403)
        result=self.clients["admin"].get(f"/api/v1/admin/accounts/{account}/credits").json()
        self.assertEqual(result["items"][0]["type"],"topup")
        self.assertEqual(self.clients["a"].get(f"/api/v1/admin/accounts/{account}/credits").status_code,403)

    def test_simulator_endpoints_not_registered_in_normal_public_app(self):
        app=create_app(Settings(database_url="sqlite+pysqlite://",public_read_only=True))
        Base.metadata.create_all(app.state.engine)
        c=TestClient(app)
        self.assertEqual(c.post("/api/v1/local-trial/login",json={"account":"admin"}).status_code,403)
        self.assertEqual(c.get("/local-trial.html").status_code,403)
        c.close();app.state.engine.dispose()


if __name__=="__main__":unittest.main()
