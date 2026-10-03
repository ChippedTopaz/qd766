import sys
import unittest
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from qd766.backend import create_app
from qd766.backend.auth import digest
from qd766.backend.config import Settings
from qd766.backend.importer import store_normalized_snapshot
from qd766.backend.models import AdminAudit, Base, LoginSession, TrialInvitation, UserAccount
from test_backend import ROOT_ID, CHILD_ID, TAY_NINH_ROOT_ID, TAY_NINH_CHILD_ID, entity, snapshot_payload


class TrialAdminTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app(Settings(database_url="sqlite+pysqlite://", public_read_only=True, require_login=True,
            invite_required=True, google_client_id="test", google_client_secret="secret",
            google_redirect_uri="https://testserver/api/v1/auth/google/callback"))
        Base.metadata.create_all(self.app.state.engine)
        self.client = TestClient(self.app, base_url="https://testserver", follow_redirects=False)
        with self.app.state.session_factory.begin() as db:
            data = snapshot_payload()
            self.peer_id = str(uuid.uuid4())
            data["datasets"][0]["children"].append(entity(self.peer_id, "Sở khác", 3))
            store_normalized_snapshot(db, data)
            store_normalized_snapshot(db, snapshot_payload(root_id=TAY_NINH_ROOT_ID, child_id=TAY_NINH_CHILD_ID))
            admin = UserAccount(external_subject="google:owner", email="vietnt89@gmail.com", display_name="Owner",
                role="admin", trial_admitted=True, root_department_id=uuid.UUID(ROOT_ID))
            db.add(admin);db.flush();self.admin_id=admin.id
            db.add(LoginSession(token_hash=digest("owner-token"), account_id=admin.id, csrf_token="csrf",
                expires_at=datetime.now(timezone.utc)+timedelta(hours=1)))
        self.client.cookies.set("qd766_session", "owner-token")
        self.headers = {"X-QD766-CSRF": "csrf"}

    def tearDown(self):
        self.client.close();self.app.state.engine.dispose()

    def invite(self, **extra):
        result = self.client.post("/api/v1/admin/invitations", json={"provinceId": ROOT_ID, **extra}, headers=self.headers)
        self.assertEqual(result.status_code, 200, result.text)
        return result.json()

    def redeem(self, token=None, sub="new", email="new@example.com", client=None):
        client = client or TestClient(self.app, base_url="https://testserver", follow_redirects=False)
        if token:
            self.assertEqual(client.post("/api/v1/auth/invite", json={"token": token}).status_code, 200)
        start = client.get("/api/v1/auth/google/start")
        state = parse_qs(urlsplit(start.headers["location"]).query)["state"][0]
        with patch("qd766.backend.auth.verify_google_identity", return_value={"sub": sub, "email": email, "name": "New"}):
            result = client.get("/api/v1/auth/google/callback", params={"state": state, "code": "code"})
        return client, result

    def test_unknown_without_invite_does_not_create_account(self):
        client, result = self.redeem()
        self.assertEqual(result.headers["location"], "/?login=invite-required")
        with self.app.state.session_factory() as db:
            self.assertEqual(db.scalar(select(func.count()).select_from(UserAccount)), 1)
        self.assertEqual(client.get("/api/v1/dashboard").status_code, 401)
        client.close()

    def test_invite_hashed_one_use_and_zero_credit_then_relogin(self):
        invite = self.invite(email="new@example.com")
        with self.app.state.session_factory() as db:
            self.assertEqual(db.get(TrialInvitation, uuid.UUID(invite["id"])).token_hash, digest(invite["token"]))
        client, result = self.redeem(invite["token"])
        self.assertEqual(result.headers["location"], "/")
        profile = client.get("/api/v1/auth/me").json()
        self.assertEqual((profile["role"], profile["credits"], profile["provinceId"]), ("user", 0, ROOT_ID))
        self.assertEqual(client.post("/api/v1/auth/invite", json={"token":invite["token"]}).status_code, 403)
        client, result = self.redeem(client=client)
        self.assertEqual(result.headers["location"], "/")
        client.close()

    def test_wrong_email_does_not_burn_invite(self):
        invite = self.invite(email="right@example.com")
        client, result = self.redeem(invite["token"])
        self.assertEqual(result.headers["location"], "/?login=invite-required")
        with self.app.state.session_factory() as db:
            self.assertIsNone(db.get(TrialInvitation, uuid.UUID(invite["id"])).used_at)
        client.close()

    def test_expired_revoked_and_expiring_during_login(self):
        invite = self.invite()
        self.assertEqual(self.client.post(f'/api/v1/admin/invitations/{invite["id"]}/revoke', headers=self.headers).status_code, 200)
        self.assertEqual(self.client.post("/api/v1/auth/invite", json={"token":invite["token"]}).status_code, 403)
        invite = self.invite()
        client = TestClient(self.app, base_url="https://testserver", follow_redirects=False)
        client.post("/api/v1/auth/invite", json={"token": invite["token"]})
        with self.app.state.session_factory.begin() as db:
            db.get(TrialInvitation, uuid.UUID(invite["id"])).expires_at = datetime.now(timezone.utc)-timedelta(seconds=1)
        _, result = self.redeem(client=client)
        self.assertEqual(result.headers["location"], "/?login=invite-required")
        client.close()

    def test_admin_csrf_and_no_operator_mutations(self):
        self.assertEqual(self.client.post("/api/v1/admin/invitations", json={"provinceId":ROOT_ID}).status_code, 403)
        for path in ("collection-control", "province-batches", "dashboard/requests"):
            self.assertEqual(self.client.post("/api/v1/"+path, json={}, headers=self.headers).status_code, 403)
        self.assertEqual(self.client.get("/api/v1/dashboard?root_department_id="+TAY_NINH_ROOT_ID).status_code, 200)
        self.assertEqual(self.client.get("/api/v1/admin/directory?provinceId="+ROOT_ID).status_code, 200)

    def test_user_cannot_admin_or_self_promote(self):
        invite = self.invite()
        client,_=self.redeem(invite["token"])
        profile=client.get("/api/v1/auth/me").json()
        for path in ("accounts", "invitations", "audit", "directory"):
            self.assertEqual(client.get("/api/v1/admin/"+path).status_code, 403)
        self.assertEqual(client.post("/api/v1/admin/accounts/"+profile["id"], json={"role":"admin"},
            headers={"X-QD766-CSRF":profile["csrfToken"]}).status_code, 403)
        client.close()

    def test_bad_unit_and_injected_role_rejected(self):
        for body in ({"provinceId":ROOT_ID,"accessTier":"agency","unitId":TAY_NINH_CHILD_ID},
                     {"provinceId":ROOT_ID,"accessTier":"agency"}, {"provinceId":ROOT_ID,"role":"admin"}):
            self.assertEqual(self.client.post("/api/v1/admin/invitations", json=body, headers=self.headers).status_code, 422)

    def test_agency_data_filtered_outside_shared_cache_and_cross_root_denied(self):
        original = self.client.get("/api/v1/dashboard?root_department_id="+ROOT_ID).json()
        invite=self.invite(accessTier="agency",unitId=CHILD_ID)
        client,_=self.redeem(invite["token"])
        filtered=client.get("/api/v1/dashboard").json()
        self.assertEqual(filtered["defaultUnitId"], CHILD_ID)
        self.assertEqual([u["departmentId"] for u in filtered["units"]], [CHILD_ID])
        for item in filtered["snapshots"].values():
            self.assertIsNone(item["provinceAggregatedScore"])
            for dataset in item["datasets"]:
                self.assertFalse(dataset["root"]["metrics"])
                self.assertIsNone(dataset["root"]["apiScore"])
                own=next(c for c in dataset["children"] if c["departmentId"]==CHILD_ID)
                self.assertTrue(own["metrics"])
                peer=next(c for c in dataset["children"] if c["departmentId"]==self.peer_id)
                self.assertFalse(peer["metrics"])
                self.assertIsNotNone(peer["apiScore"])
        self.assertEqual(self.client.get("/api/v1/dashboard?root_department_id="+ROOT_ID).json(), original)
        self.assertEqual(client.get("/api/v1/dashboard?root_department_id="+TAY_NINH_ROOT_ID).status_code, 403)
        selection=client.get("/api/v1/dashboard/selection?period_type=month&year=2026&period_value=8").json()
        self.assertFalse(selection["snapshot"]["datasets"][0]["root"]["metrics"])
        rankings=client.get("/api/v1/dashboard/province-rankings?period_type=month&year=2026&period_value=8").json()
        self.assertTrue(all(not g["metrics"] for r in rankings for g in r["groups"].values()))
        client.close()

    def test_lock_revokes_sessions_audits_and_cannot_lock_owner(self):
        invite=self.invite();client,_=self.redeem(invite["token"])
        account_id=client.get("/api/v1/auth/me").json()["id"]
        body={"provinceId":ROOT_ID,"active":False}
        self.assertEqual(self.client.post("/api/v1/admin/accounts/"+account_id,json=body,headers=self.headers).status_code,200)
        self.assertEqual(client.get("/api/v1/auth/me").status_code,401)
        self.assertEqual(self.client.post("/api/v1/admin/accounts/"+str(self.admin_id),json=body,headers=self.headers).status_code,403)
        with self.app.state.session_factory() as db:
            self.assertEqual(db.get(UserAccount,uuid.UUID(account_id)).credit_balance,0)
            self.assertTrue(db.scalar(select(AdminAudit).where(AdminAudit.action=="account.updated")))
        client.close()

    def test_old_uninvited_session_is_blocked(self):
        with self.app.state.session_factory.begin() as db:
            account=UserAccount(external_subject="google:old",display_name="Old",root_department_id=uuid.UUID(ROOT_ID))
            db.add(account);db.flush()
            db.add(LoginSession(token_hash=digest("old-token"),account_id=account.id,csrf_token="old",
                expires_at=datetime.now(timezone.utc)+timedelta(hours=1)))
        self.client.cookies.set("qd766_session","old-token")
        self.assertEqual(self.client.get("/api/v1/auth/me").status_code,403)
        self.assertEqual(self.client.get("/api/v1/dashboard").status_code,403)


if __name__ == "__main__":
    unittest.main()
