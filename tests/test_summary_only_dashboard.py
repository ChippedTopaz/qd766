import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
from sqlalchemy import select, func
from fastapi.testclient import TestClient

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"src"))
from qd766.backend import create_app
from qd766.backend.config import Settings
from qd766.backend.models import Base, CollectionJob
from qd766.backend.importer import store_normalized_snapshot
from qd766.backend.national_summaries import store_national_summary
from qd766.national_summary import NationalSummaryCapture
from qd766.periods import PeriodSelection
from test_backend import snapshot_payload, ROOT_ID
from test_national_summary import response_body


class SummaryOnlyDashboardTests(unittest.TestCase):
    def setUp(self):
        self.app=create_app(Settings(database_url="sqlite+pysqlite://",public_read_only=True))
        Base.metadata.create_all(self.app.state.engine)
        self.client=TestClient(self.app)
        with self.app.state.session_factory.begin() as db:
            store_normalized_snapshot(db,snapshot_payload())
            for value in (9,10):
                body=response_body()["data"]
                store_national_summary(db,NationalSummaryCapture(
                    PeriodSelection("month",2026,value),{},body,str(value%10)*64,
                    datetime(2026,10,2,16,tzinfo=timezone.utc)))

    def tearDown(self):
        self.app.state.engine.dispose()

    def test_missing_details_have_six_scores_no_invented_child_data_or_jobs(self):
        response=self.client.get("/api/v1/dashboard/selection",params={
            "period_type":"month","year":2026,"period_value":10,"root_department_id":ROOT_ID})
        self.assertEqual(response.status_code,200)
        snap=response.json()["snapshot"]
        self.assertFalse(snap["delivery"]["detailsAvailable"])
        self.assertIsNone(snap["delivery"]["detailsCapturedAt"])
        self.assertEqual(snap["provinceAggregatedScore"],61.86)
        self.assertEqual(len(snap["datasets"]),6)
        for dataset in snap["datasets"]:
            self.assertEqual(dataset["children"],[])
            self.assertEqual(dataset["root"]["metrics"],[])
            self.assertEqual(dataset["root"]["parameters"],{})
            self.assertIsNotNone(dataset["root"]["apiScore"])
        rankings=self.client.get("/api/v1/dashboard/province-rankings",params={
            "period_type":"month","year":2026,"period_value":10})
        self.assertEqual(len(rankings.json()),34)
        with self.app.state.session_factory() as db:
            self.assertEqual(db.scalar(select(func.count()).select_from(CollectionJob)),0)
        # Summary-only must not make a missing paid/formality scope readable.
        denied=self.client.get("/api/v1/dashboard/selection",params={
            "period_type":"month","year":2026,"period_value":10,"scope":"formality","root_department_id":ROOT_ID})
        self.assertEqual(denied.status_code,403)

    def test_dashboard_includes_saved_history_and_preserves_existing_detail(self):
        response=self.client.get("/api/v1/dashboard",params={"root_department_id":ROOT_ID})
        self.assertEqual(response.status_code,200)
        payload=response.json()
        self.assertIn("month-2026-09:all",payload["snapshots"])
        self.assertIn("month-2026-10:all",payload["snapshots"])
        self.assertEqual(len(payload["snapshots"]["month-2026-08:all"]["datasets"][0]["children"]),1)
        self.assertEqual(payload["snapshots"]["month-2026-10:all"]["datasets"][0]["children"],[])
        missing=self.client.get("/api/v1/dashboard/selection",params={
            "period_type":"month","year":2026,"period_value":7,"root_department_id":ROOT_ID})
        self.assertEqual(missing.status_code,404)
