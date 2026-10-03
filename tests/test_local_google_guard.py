from dataclasses import replace
import sys
from pathlib import Path
import unittest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/"src"))
from qd766.backend.app import create_app
from qd766.backend.auth import validate_auth_settings
from qd766.backend.config import Settings


class LocalGoogleGuardTests(unittest.TestCase):
    def setUp(self):
        self.settings = Settings(database_url="postgresql+psycopg://test@127.0.0.1/qd766_credit_test",
            local_google_trial=True, public_read_only=True, require_login=True,
            google_client_id="test-client", google_client_secret="test-secret",
            google_redirect_uri="http://127.0.0.1:8771/api/v1/auth/google/callback")

    def test_only_explicit_local_test_mode_allows_http_google(self):
        validate_auth_settings(self.settings)
        with self.assertRaises(ValueError):
            validate_auth_settings(replace(self.settings,local_google_trial=False))

    def test_rejects_production_db_remote_host_or_wrong_callback(self):
        for settings in (replace(self.settings,database_url="postgresql+psycopg://test@127.0.0.1/qd766"),
                         replace(self.settings,database_url="postgresql+psycopg://test@external.example/qd766_credit_test"),
                         replace(self.settings,google_redirect_uri="http://127.0.0.1:8769/api/v1/auth/google/callback")):
            with self.assertRaises(ValueError):
                validate_auth_settings(settings)

    def test_loopback_guard_without_connecting_database(self):
        app=create_app(self.settings)
        try:
            with TestClient(app,base_url="http://127.0.0.1:8771",client=("127.0.0.1",123)) as client:
                self.assertEqual(client.get("/api/v1/health/live").status_code,200)
                self.assertEqual(client.get("/api/v1/access-policy").json()["localGoogleTrial"],True)
                self.assertEqual(client.get("/api/v1/health/live",headers={"Origin":"https://evil.example"}).status_code,403)
            with TestClient(app,base_url="http://127.0.0.1:8771",client=("192.168.1.10",123)) as client:
                self.assertEqual(client.get("/api/v1/health/live").status_code,403)
        finally:
            app.state.engine.dispose()
