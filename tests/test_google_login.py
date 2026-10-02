import sys
import unittest
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlsplit
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from fastapi.testclient import TestClient
from sqlalchemy import select, func
from qd766.backend import create_app
from qd766.backend.auth import digest, validate_google_claims
from qd766.backend.config import Settings
from qd766.backend.importer import store_normalized_snapshot
from qd766.backend.models import Base, LoginAttempt, LoginSession, UserAccount


class GoogleLoginTests(unittest.TestCase):
    def setUp(self):
        self.settings = Settings(database_url="sqlite+pysqlite://", public_read_only=True, require_login=True,
            google_client_id="test-client", google_client_secret="test-secret",
            google_redirect_uri="https://testserver/api/v1/auth/google/callback")
        self.app = create_app(self.settings)
        Base.metadata.create_all(self.app.state.engine)
        self.client = TestClient(self.app, base_url="https://testserver", follow_redirects=False)
        self.identity = {"sub": "123", "email": "test@example.com", "name": "Test User"}

    def tearDown(self):
        self.client.close()
        self.app.state.engine.dispose()

    def start_login(self):
        response = self.client.get("/api/v1/auth/google/start")
        self.assertEqual(response.status_code, 303)
        params = parse_qs(urlsplit(response.headers["location"]).query)
        self.assertEqual(params["scope"], ["openid email profile"])
        self.assertEqual(params["code_challenge_method"], ["S256"])
        self.assertIn("HttpOnly", response.headers["set-cookie"])
        self.assertIn("Secure", response.headers["set-cookie"])
        return params["state"][0]

    def login(self):
        state = self.start_login()
        with patch("qd766.backend.auth.verify_google_identity", return_value=self.identity):
            response = self.client.get("/api/v1/auth/google/callback", params={"state": state, "code": "one-time-code"})
        self.assertEqual(response.headers["location"], "/")
        return state

    def test_new_account_is_free_zero_credit_unassigned_and_token_is_hashed(self):
        self.login()
        profile = self.client.get("/api/v1/auth/me").json()
        self.assertEqual(profile["plan"], "free")
        self.assertEqual(profile["credits"], 0)
        self.assertIsNone(profile["provinceId"])
        token = self.client.cookies.get("qd766_session")
        with self.app.state.session_factory() as db:
            self.assertIsNotNone(db.get(LoginSession, digest(token)))
            self.assertIsNone(db.get(LoginSession, token))
        self.assertEqual(self.client.get("/api/v1/dashboard").status_code, 403)

    def test_state_binding_replay_and_invalid_claims_fail_closed(self):
        state = self.start_login()
        other = TestClient(self.app, base_url="https://testserver", follow_redirects=False)
        with patch("qd766.backend.auth.verify_google_identity") as verify:
            response = other.get("/api/v1/auth/google/callback", params={"state": state, "code": "stolen"})
            self.assertEqual(response.headers["location"], "/?login=failed")
            verify.assert_not_called()
        other.close()
        with patch("qd766.backend.auth.verify_google_identity", side_effect=ValueError("bad signature")):
            self.client.get("/api/v1/auth/google/callback", params={"state": state, "code": "invalid"})
        with patch("qd766.backend.auth.verify_google_identity") as verify:
            self.client.get("/api/v1/auth/google/callback", params={"state": state, "code": "replay"})
            verify.assert_not_called()
        self.assertEqual(self.client.get("/api/v1/auth/me").status_code, 401)

    def test_repeated_login_keeps_plan_credit_and_single_identity(self):
        old_state = self.login()
        old_token = self.client.cookies.get("qd766_session")
        with self.app.state.session_factory.begin() as db:
            account = db.scalar(select(UserAccount))
            account.plan = "paid"; account.credit_balance = 70
        self.login()
        self.assertEqual(self.client.get("/api/v1/auth/me").json()["credits"], 70)
        with self.app.state.session_factory() as db:
            self.assertEqual(db.scalar(select(func.count()).select_from(UserAccount)), 1)
            self.assertIsNone(db.get(LoginSession, digest(old_token)))
            self.assertEqual(db.scalar(select(UserAccount)).plan, "paid")
        with patch("qd766.backend.auth.verify_google_identity") as verify:
            self.client.get("/api/v1/auth/google/callback", params={"state": old_state, "code": "replay"})
            verify.assert_not_called()

    def test_expired_or_cancelled_login_does_not_exchange_code(self):
        state = self.start_login()
        with self.app.state.session_factory.begin() as db:
            db.get(LoginAttempt, digest(state)).expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        with patch("qd766.backend.auth.verify_google_identity") as verify:
            self.client.get("/api/v1/auth/google/callback", params={"state": state, "code": "expired"})
            verify.assert_not_called()
        state = self.start_login()
        with patch("qd766.backend.auth.verify_google_identity") as verify:
            self.client.get("/api/v1/auth/google/callback", params={"state": state, "error": "access_denied"})
            verify.assert_not_called()
        self.assertEqual(self.client.get("/api/v1/auth/me").status_code, 401)

    def test_session_expiry_disable_and_logout_csrf(self):
        self.login()
        profile = self.client.get("/api/v1/auth/me").json()
        self.assertEqual(self.client.post("/api/v1/auth/logout").status_code, 403)
        self.assertEqual(self.client.post("/api/v1/auth/logout", headers={"X-QD766-CSRF": profile["csrfToken"]}).status_code, 303)
        self.assertEqual(self.client.get("/api/v1/auth/me").status_code, 401)
        self.login()
        with self.app.state.session_factory.begin() as db:
            db.scalar(select(LoginSession)).expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        self.assertEqual(self.client.get("/api/v1/auth/me").status_code, 401)
        self.login()
        with self.app.state.session_factory.begin() as db:
            db.scalar(select(UserAccount)).active = False
        self.assertEqual(self.client.get("/api/v1/auth/me").status_code, 401)
        self.assertEqual(self.client.get("/api/v1/dashboard").status_code, 401)

    def test_province_is_server_assigned_and_cross_province_is_blocked(self):
        from test_backend import snapshot_payload, ROOT_ID, TAY_NINH_ROOT_ID, TAY_NINH_CHILD_ID
        self.assertEqual(self.client.get("/api/v1/dashboard").status_code, 401)
        self.login()
        with self.app.state.session_factory.begin() as db:
            store_normalized_snapshot(db, snapshot_payload())
            store_normalized_snapshot(db, snapshot_payload(root_id=TAY_NINH_ROOT_ID, root_name="UBND tỉnh Tây Ninh", child_id=TAY_NINH_CHILD_ID))
            db.scalar(select(UserAccount)).root_department_id = uuid.UUID(ROOT_ID)
        response = self.client.get("/api/v1/dashboard")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["province"]["id"], ROOT_ID)
        for query in [str(uuid.uuid4()), f"{ROOT_ID}&root_department_id={uuid.uuid4()}"]:
            self.assertEqual(self.client.get(f"/api/v1/dashboard?root_department_id={query}").status_code, 403)
        provinces = self.client.get("/api/v1/dashboard/provinces").json()
        self.assertTrue(all(item["id"] == ROOT_ID for item in provinces))
        comparison = self.client.get("/api/v1/dashboard/province-rankings?period_type=month&year=2026&period_value=8").json()
        other = next(item for item in comparison if item["rootDepartmentId"] == TAY_NINH_ROOT_ID)
        self.assertTrue(all(not group["metrics"] and not group["parameters"] for group in other["groups"].values()))
        self.assertEqual(self.client.get("/api/v1/dashboard?scope=formality").status_code, 403)
        self.assertEqual(self.client.post("/api/v1/formality-batches", json={"accountId": "fake", "plan": "admin"}).status_code, 403)

    def test_claims_and_config_validation(self):
        valid = {**self.identity, "iss": "https://accounts.google.com", "aud": "test-client", "nonce": "nonce", "email_verified": True}
        self.assertEqual(validate_google_claims(valid, "nonce", "test-client")["sub"], "123")
        for key, value in [("iss", "https://evil.example"), ("aud", "other"), ("nonce", "wrong"), ("email_verified", False), ("sub", "")]:
            with self.assertRaises(ValueError):
                validate_google_claims({**valid, key: value}, "nonce", "test-client")
        self.assertNotIn("test-secret", repr(self.settings))
        for settings in [Settings(require_login=True), Settings(google_client_id="partial"),
                Settings(public_read_only=True, google_client_id="x", google_client_secret="y", google_redirect_uri="http://example.com/api/v1/auth/google/callback")]:
            with self.assertRaises(ValueError):
                create_app(settings)


if __name__ == "__main__":
    unittest.main()
