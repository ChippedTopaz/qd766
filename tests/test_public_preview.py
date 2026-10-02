import os
import sys
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from fastapi.testclient import TestClient
from qd766.backend.app import create_app
from qd766.backend.config import Settings
from qd766.backend.importer import store_normalized_snapshot
from qd766.backend.models import Base, Formality


class PublicPreviewTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app(Settings(database_url="sqlite+pysqlite://", public_read_only=True))
        self.client = TestClient(self.app)

    def tearDown(self):
        self.client.close()
        self.app.state.engine.dispose()

    def test_public_policy_and_health_without_authentication_claim(self):
        policy = self.client.get("/api/v1/access-policy")
        self.assertEqual(policy.status_code, 200)
        self.assertEqual(policy.json(), {"publicReadOnly": True, "loginRequired": False, "googleLoginEnabled": False, "paidRequestsEnabled": False})
        self.assertEqual(self.client.get("/api/v1/health/live").status_code, 200)

    def test_block_writes_and_operator_or_raw_reads_before_database_access(self):
        for method in ["POST", "PUT", "PATCH", "DELETE"]:
            for path in ["/api/v1/dashboard/collection-requests", "/api/v1/formality-batches", "/api/v1/access-policy"]:
                with self.subTest(method=method, path=path):
                    self.assertEqual(self.client.request(method, path, json={}).status_code, 403)
        for path in ["/api/v1/collection-jobs", "/api/v1/system-status", "/api/v1/snapshots", "/api/v1/formalities", "/api/v1/province-catalog/25/preview", "/api/v1/new-unreviewed-endpoint"]:
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 403)

    def test_block_formality_scope_and_duplicate_query_bypass(self):
        for query in ["scope=formality", "scope=all&scope=formality", "scope=formality&scope=all", "scope=ALL", "formality_id=", "formalityId=abc"]:
            self.assertEqual(self.client.get(f"/api/v1/dashboard?{query}").status_code, 403)

    def test_static_fixture_and_documentation_are_not_public(self):
        for path in ["/data/snapshots.json", "/%64ata/snapshots.json", "/docs", "/openapi.json", "/dist/app.js.map"]:
            self.assertEqual(self.client.get(path).status_code, 403)
        for path in ["/", "/styles.css", "/dist/app.js", "/vendor/exceljs/exceljs.min.js"]:
            self.assertEqual(self.client.get(path).status_code, 200)

    def test_dashboard_does_not_embed_paid_snapshots_in_all_response(self):
        from test_backend import snapshot_payload
        Base.metadata.create_all(self.app.state.engine)
        payload = snapshot_payload()
        with self.app.state.session_factory.begin() as session:
            store_normalized_snapshot(session, payload)
            formality_id = uuid.uuid4()
            session.add(Formality(id=formality_id, code="TEST-PAID", name="Private test procedure"))
            session.flush()
            payload["scope"] = "formality"
            payload["formalityId"] = str(formality_id)
            for dataset in payload["datasets"]:
                dataset["scope"] = "formality"
                dataset["formalityId"] = str(formality_id)
            store_normalized_snapshot(session, payload)
        response = self.client.get("/api/v1/dashboard")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["snapshots"])
        self.assertTrue(all(item["scope"] == "all" for item in response.json()["snapshots"].values()))
        self.assertNotIn("TEST-PAID", response.text)
        self.assertNotIn(str(formality_id), response.text)

    def test_office_mode_and_configuration_are_preserved(self):
        office = create_app(Settings(database_url="sqlite+pysqlite:///:memory:"))
        with TestClient(office) as client:
            self.assertFalse(client.get("/api/v1/access-policy").json()["publicReadOnly"])
            self.assertEqual(client.get("/docs").status_code, 200)
        office.state.engine.dispose()
        with patch.dict(os.environ, {"QD766_PUBLIC_READ_ONLY": "true"}):
            self.assertTrue(Settings.from_env().public_read_only)
        with self.assertRaises(ValueError):
            create_app(Settings(public_read_only=True, cors_origins=("*",)))


if __name__ == "__main__":
    unittest.main()
