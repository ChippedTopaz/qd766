import os
import sys
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from fastapi.testclient import TestClient
from qd766.backend.app import create_app
from qd766.backend.models import Base
from qd766.backend.public_deployment import CALLBACK, read_config, public_settings


class PublicDeploymentTests(unittest.TestCase):
    def setUp(self):
        self.office = {"QD766_DATABASE_PASSWORD": "fake-db-password",
                       "QD766_PUBLIC_READ_ONLY": "false", "QD766_SQL_ECHO": "true",
                       "QD766_PAID_REQUESTS_ENABLED": "true", "QD766_CORS_ORIGINS": "*"}
        self.public = {"QD766_GOOGLE_CLIENT_ID": "test.apps.googleusercontent.com",
                       "QD766_GOOGLE_CLIENT_SECRET": "fake-client-secret",
                       "QD766_GOOGLE_REDIRECT_URI": CALLBACK}

    def test_operator_and_process_flags_cannot_weaken_boundary(self):
        with patch.dict(os.environ, self.office):
            settings = public_settings(self.office, self.public)
        self.assertTrue(settings.public_read_only and settings.require_login)
        self.assertFalse(settings.paid_requests_enabled or settings.trial_credits_enabled or settings.sql_echo)
        self.assertEqual(settings.formality_credit_cost, 0)
        self.assertEqual(settings.cors_origins, ())
        self.assertIn("127.0.0.1", settings.database_url)
        self.assertEqual(self.office["QD766_PUBLIC_READ_ONLY"], "false")

    def test_invalid_auth_or_override_fails_closed(self):
        cases = [dict(self.public, QD766_REQUIRE_LOGIN="false"),
                 dict(self.public, QD766_GOOGLE_CLIENT_SECRET=""),
                 dict(self.public, QD766_GOOGLE_CLIENT_ID="<placeholder>"),
                 dict(self.public, QD766_GOOGLE_REDIRECT_URI="http://127.0.0.1:8767/api/v1/auth/google/callback"),
                 dict(self.public, QD766_GOOGLE_REDIRECT_URI=CALLBACK + "?secret=bad")]
        for config in cases:
            with self.subTest(keys=list(config)):
                with self.assertRaises(ValueError):
                    public_settings(self.office, config)

    def test_nonlocal_or_nonpostgres_database_rejected(self):
        for url in ["sqlite+pysqlite://", "postgresql+psycopg://user:secret@remote/qd766"]:
            with self.assertRaises(ValueError):
                public_settings(dict(self.office, QD766_DATABASE_URL=url), self.public)

    def test_public_app_blocks_admin_writes_and_requires_login(self):
        settings = replace(public_settings(self.office, self.public), database_url="sqlite+pysqlite://")
        app = create_app(settings)
        Base.metadata.create_all(app.state.engine)
        try:
            with TestClient(app) as client:
                self.assertEqual(client.get("/api/v1/health/live").status_code, 200)
                self.assertEqual(client.get("/api/v1/dashboard").status_code, 401)
                for path in ["/api/v1/system-status", "/docs", "/openapi.json", "/.env.public", "/data/snapshots.json"]:
                    self.assertEqual(client.get(path).status_code, 403)
                for path in ["/api/v1/dashboard/collection-requests", "/api/v1/me/collection-quote",
                             "/api/v1/me/formality-requests", "/api/v1/collection-control"]:
                    self.assertEqual(client.post(path, json={}).status_code, 403)
        finally:
            app.state.engine.dispose()

    def test_config_parser_rejects_duplicates_without_leaking_values(self):
        with patch.object(Path, "read_text", return_value="KEY=secret-one\nKEY=secret-two\n"):
            with self.assertRaises(ValueError) as error:
                read_config(Path("unused"))
            self.assertNotIn("secret", str(error.exception))
