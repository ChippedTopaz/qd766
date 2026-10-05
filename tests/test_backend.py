import copy
import sys
import unittest
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from fastapi.testclient import TestClient
from sqlalchemy import func, select

from qd766.backend import create_app
from qd766.backend.config import Settings
from qd766.backend.dashboard import _detail_snapshot_is_stale
from qd766.backend.importer import (
    SnapshotImportError,
    store_formality_page,
    store_normalized_snapshot,
)
from qd766.backend.jobs import (
    close_collection_circuit,
    JobStateError,
    claim_next_job,
    enqueue_job,
    halt_job,
    open_collection_circuit,
    retry_or_fail_job,
    succeed_job,
)
from qd766.backend.national_summaries import store_national_summary
from qd766.backend.models import (
    Base,
    CollectionControl,
    CollectionJob,
    Dataset,
    Department,
    Entity,
    Formality,
    Metric,
    ProvinceCollectionBatch,
    ProvinceCollectionBatchItem,
    Snapshot,
)
from qd766.backend.province_batches import create_province_batch, resume_province_batch
from qd766.backend.province_refresh import choose_detail_refresh_period
from qd766.backend.worker import run_one_job
from qd766.collection import SafetyStop
from qd766.national_summary import NationalSummaryCapture
from qd766.periods import PeriodSelection
from qd766.province_roots import ProvinceRoot

ROOT_ID = "019d2be3-6a88-732b-8b17-b68020c8553a"
CHILD_ID = "019d2be3-6a88-732b-8b17-bb1e9a3f14ab"
TAY_NINH_ROOT_ID = "019d2be3-6a88-732b-8b23-f5575505c632"
TAY_NINH_CHILD_ID = "019d2be3-6a88-732b-8b23-f5575505c633"
HA_NOI_ROOT_ID = "019d2be3-6a86-70a8-a0af-76e986804225"


def entity(department_id, name, score):
    return {
        "departmentId": department_id,
        "departmentName": name,
        "departmentCode": "H44",
        "departmentType": "PROVINCE",
        "departmentLevel": "PROVINCE",
        "agencyLevel": "level_1",
        "apiScore": score,
        "apiMaxScore": 10,
        "apiRatio": 50,
        "scoreSource": "dvcqg-api",
        "formulaApplied": False,
        "metrics": [
            {
                "code": "EXAMPLE",
                "name": "Example",
                "numerator": 1,
                "denominator": 2,
                "ratio": 50,
                "apiScore": score,
                "apiMaxScore": 10,
                "extras": {},
            }
        ],
        "parameters": {},
        "metadata": {},
    }


class DetailFreshnessTest(unittest.TestCase):
    def snapshot(self, *, period_type, year, period_value, created_at):
        return Snapshot(
            snapshot_key=f"test:{period_type}:{year}:{period_value}",
            schema_version=1,
            root_department_id=uuid.uuid4(),
            period_type=period_type,
            year=year,
            period_value=period_value,
            scope="all",
            formality_id=None,
            state="complete",
            policy={},
            status_detail={},
            created_at=created_at,
        )

    def test_open_period_detail_expires_after_72_hours(self):
        now = datetime(2026, 10, 2, 3, 0, tzinfo=timezone.utc)
        snapshot = self.snapshot(
            period_type="month",
            year=2026,
            period_value=10,
            created_at=now - timedelta(hours=73),
        )
        self.assertTrue(_detail_snapshot_is_stale(snapshot, now))

    def test_closed_period_detail_never_expires(self):
        now = datetime(2026, 10, 2, 3, 0, tzinfo=timezone.utc)
        snapshot = self.snapshot(
            period_type="month",
            year=2026,
            period_value=9,
            created_at=now - timedelta(days=30),
        )
        self.assertFalse(_detail_snapshot_is_stale(snapshot, now))


def snapshot_payload(
    root_id=ROOT_ID,
    root_name="UBND tỉnh Phú Thọ",
    child_id=CHILD_ID,
    child_name="Văn phòng UBND",
):
    return {
        "schemaVersion": 1,
        "period": {"type": "month", "year": 2026, "month": 8},
        "scope": "all",
        "formalityId": None,
        "status": {
            "state": "complete",
            "requiredGroups": ["transparency"],
            "loadedGroups": ["transparency"],
            "unsupportedGroups": [],
            "missingGroups": [],
        },
        "scorePolicy": {"authoritativeValue": "apiScore"},
        "provinceAggregatedScore": 5,
        "provinceAggregatedMaximum": 10,
        "datasets": [
            {
                "group": "transparency",
                "schemaKind": "metrics",
                "formulaStatus": "metrics-returned-by-api",
                "scorePolicy": "api-authoritative",
                "period": {"type": "month", "year": 2026, "month": 8},
                "scope": "all",
                "formalityId": None,
                "root": entity(root_id, root_name, 5),
                "children": [entity(child_id, child_name, 4)],
                "details": {"source": "fixture"},
                "raw": {"path": "transparency/month-all.json", "sha256": "a" * 64},
            }
        ],
    }


class BackendTest(unittest.TestCase):
    def setUp(self):
        self.app = create_app(Settings(database_url="sqlite+pysqlite://"))
        Base.metadata.create_all(self.app.state.engine)
        self.client = TestClient(self.app)

    def tearDown(self):
        Base.metadata.drop_all(self.app.state.engine)
        self.app.state.engine.dispose()

    def test_health_and_empty_snapshot_list(self):
        self.assertEqual(self.client.get("/api/v1/health/live").json(), {"status": "ok"})
        self.assertEqual(self.client.get("/api/v1/health/ready").status_code, 200)
        self.assertEqual(self.client.get("/api/v1/snapshots").json(), [])

    def test_database_password_is_safely_encoded(self):
        with patch.dict(
            "os.environ",
            {
                "QD766_DATABASE_PASSWORD": "example@password:with/symbols",
                "QD766_DATABASE_USER": "qd766_app",
            },
            clear=True,
        ):
            url = Settings.from_env().database_url
        self.assertIn("example%40password%3Awith%2Fsymbols", url)
        self.assertIn("@127.0.0.1:5432/qd766", url)

    def test_immutable_observation_id_resume_and_new_daily_capture(self):
        with self.app.state.session_factory.begin() as db:
            old=store_normalized_snapshot(db,snapshot_payload())
            first=store_normalized_snapshot(db,snapshot_payload(),observation_id='daily-1')
            resumed=store_normalized_snapshot(db,snapshot_payload(),observation_id='daily-1')
            next_day=store_normalized_snapshot(db,snapshot_payload(),observation_id='daily-2')
            self.assertEqual(first.id,resumed.id)
            self.assertNotEqual(old.id,first.id)
            self.assertNotEqual(first.id,next_day.id)
            self.assertEqual(db.scalar(select(func.count()).select_from(Snapshot)),3)

    def test_import_is_atomic_queryable_and_idempotent(self):
        with self.app.state.session_factory.begin() as session:
            first = store_normalized_snapshot(session, snapshot_payload())
            first_id = first.id
        with self.app.state.session_factory.begin() as session:
            second = store_normalized_snapshot(session, snapshot_payload())
            self.assertEqual(second.id, first_id)
            self.assertEqual(session.scalar(select(func.count()).select_from(Snapshot)), 1)
            self.assertEqual(session.scalar(select(func.count()).select_from(Dataset)), 1)
            self.assertEqual(session.scalar(select(func.count()).select_from(Entity)), 2)
            self.assertEqual(session.scalar(select(func.count()).select_from(Metric)), 2)

        response = self.client.get(
            "/api/v1/snapshots/latest",
            params={
                "root_department_id": ROOT_ID,
                "period_type": "month",
                "year": 2026,
                "period_value": 8,
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["provinceAggregatedScore"], "5.0000")
        datasets = self.client.get(f"/api/v1/snapshots/{first_id}/datasets").json()
        self.assertEqual(datasets[0]["group"], "transparency")
        entities = self.client.get(f"/api/v1/datasets/{datasets[0]['id']}/entities").json()
        self.assertEqual(len(entities), 2)
        self.assertEqual(entities[0]["metrics"][0]["code"], "EXAMPLE")
        dashboard = self.client.get("/api/v1/dashboard")
        self.assertEqual(dashboard.status_code, 200)
        self.assertEqual(dashboard.headers["X-QD766-Cache"], "miss")
        dashboard_body = dashboard.json()
        self.assertEqual(dashboard_body["defaultUnitId"], ROOT_ID)
        self.assertEqual(len(dashboard_body["units"]), 2)
        month_period = next(
            item for item in dashboard_body["periods"] if item["id"] == "month-2026-08"
        )
        self.assertEqual(month_period["value"], 8)
        stored_dataset = dashboard_body["snapshots"]["month-2026-08:all"]["datasets"][0]
        self.assertEqual(stored_dataset["group"], "transparency")
        self.assertEqual(stored_dataset["children"][0]["metrics"][0]["code"], "EXAMPLE")
        self.assertIn("capturedAt", stored_dataset["capture"])
        cached = self.client.get("/api/v1/dashboard")
        self.assertEqual(cached.headers["X-QD766-Cache"], "hit")
        selection = self.client.get(
            "/api/v1/dashboard/selection",
            params={
                "period_type": "month",
                "year": 2026,
                "period_value": 8,
                "scope": "all",
            },
        )
        self.assertEqual(selection.status_code, 200)
        self.assertEqual(selection.json()["metadata"]["result"], "database")
        self.assertEqual(selection.json()["snapshot"]["scope"], "all")
        missing_selection = self.client.get(
            "/api/v1/dashboard/selection",
            params={
                "period_type": "month",
                "year": 2026,
                "period_value": 7,
                "scope": "all",
            },
        )
        self.assertEqual(missing_selection.status_code, 404)
        available_request = self.client.post(
            "/api/v1/dashboard/requests",
            json={
                "periodType": "month",
                "year": 2026,
                "periodValue": 8,
                "scope": "all",
            },
        )
        self.assertEqual(available_request.status_code, 403)
        system_status = self.client.get("/api/v1/system-status").json()
        self.assertEqual(system_status["snapshotCount"], 1)
        self.assertEqual(system_status["dashboardCache"]["entries"], 2)

    def test_dashboard_can_list_and_switch_provinces(self):
        with self.app.state.session_factory.begin() as session:
            store_normalized_snapshot(session, snapshot_payload())
            store_normalized_snapshot(
                session,
                snapshot_payload(
                    root_id=TAY_NINH_ROOT_ID,
                    root_name="UBND tỉnh Tây Ninh",
                    child_id=TAY_NINH_CHILD_ID,
                    child_name="Văn phòng UBND tỉnh Tây Ninh",
                ),
            )

        provinces = self.client.get("/api/v1/dashboard/provinces")
        self.assertEqual(provinces.status_code, 200)
        by_id = {item["id"]: item for item in provinces.json()}
        self.assertEqual(len(by_id), 34)
        self.assertEqual(by_id[ROOT_ID]["provinceCode"], "25")
        self.assertEqual(by_id[TAY_NINH_ROOT_ID]["provinceCode"], "80")
        self.assertTrue(by_id[ROOT_ID]["available"])
        self.assertFalse(by_id[HA_NOI_ROOT_ID]["available"])

        tay_ninh = self.client.get(
            "/api/v1/dashboard",
            params={"root_department_id": TAY_NINH_ROOT_ID},
        )
        self.assertEqual(tay_ninh.status_code, 200)
        self.assertEqual(tay_ninh.json()["province"]["code"], "80")
        self.assertEqual(tay_ninh.json()["defaultUnitId"], TAY_NINH_ROOT_ID)

        rankings = self.client.get(
            "/api/v1/dashboard/province-rankings",
            params={
                "period_type": "month",
                "year": 2026,
                "period_value": 8,
                "scope": "all",
            },
        )
        self.assertEqual(rankings.status_code, 200)
        ranking_by_id = {item["rootDepartmentId"]: item for item in rankings.json()}
        self.assertEqual(set(ranking_by_id), {ROOT_ID, TAY_NINH_ROOT_ID})
        self.assertEqual(ranking_by_id[ROOT_ID]["provinceName"], "UBND tỉnh Phú Thọ")
        self.assertEqual(ranking_by_id[ROOT_ID]["totalScore"], 5.0)
        self.assertEqual(ranking_by_id[ROOT_ID]["totalMaximum"], 10.0)
        self.assertEqual(
            ranking_by_id[ROOT_ID]["groups"]["transparency"]["score"],
            5.0,
        )
        self.assertEqual(
            ranking_by_id[ROOT_ID]["groups"]["transparency"]["metrics"]["EXAMPLE"]["score"],
            5.0,
        )

        queued = self.client.post(
            "/api/v1/dashboard/requests",
            json={
                "periodType": "quarter",
                "year": 2026,
                "periodValue": 2,
                "scope": "all",
                "provinceCode": "80",
            },
        )
        self.assertEqual(queued.status_code, 403)
        with self.app.state.session_factory() as session:
            self.assertIsNone(session.scalar(select(CollectionJob)))

    def test_national_summary_overlays_province_score_and_rankings(self):
        with self.app.state.session_factory.begin() as session:
            store_normalized_snapshot(session, snapshot_payload())
            capture = NationalSummaryCapture(
                period=PeriodSelection("month", 2026, 8),
                request_payload={
                    "timeType": "month",
                    "year": 2026,
                    "month": 8,
                    "departmentType": "ADMINISTRATIVE_UNIT",
                },
                response_data={
                    "overview": {
                        "departmentName": "Cả nước",
                        "totalScore": 61.51,
                        "totalMaxScore": 100,
                        "ratio": 61.51,
                    },
                    "evaluation": [
                        {
                            "departmentId": ROOT_ID,
                            "departmentName": "UBND tỉnh Phú Thọ",
                            "departmentCode": "H44",
                            "totalScore": 61.86,
                            "ratio": 61.86,
                            "scoreDelta": 18.02,
                            "groupScores": {
                                "CKMB": 7.96,
                                "TDGQ": 17.68,
                                "CLGQ": 8.56,
                                "TTTT": 6.67,
                                "MDHL": 11.37,
                                "MDSH": 9.62,
                            },
                        },
                        {
                            "departmentId": TAY_NINH_ROOT_ID,
                            "departmentName": "UBND tỉnh Tây Ninh",
                            "departmentCode": "H72",
                            "totalScore": 60.0,
                            "ratio": 60.0,
                            "scoreDelta": 1.0,
                            "groupScores": {
                                "CKMB": 8.0,
                                "TDGQ": 17.0,
                                "CLGQ": 8.0,
                                "TTTT": 6.0,
                                "MDHL": 11.0,
                                "MDSH": 10.0,
                            },
                        },
                    ],
                },
                raw_sha256="a" * 64,
                captured_at=datetime(2026, 10, 1, 12, 0, tzinfo=timezone.utc),
            )
            first, created = store_national_summary(session, capture)
            self.assertTrue(created)
            second, created = store_national_summary(session, capture)
            self.assertFalse(created)
            self.assertEqual(first.id, second.id)

        selection = self.client.get(
            "/api/v1/dashboard/selection",
            params={
                "period_type": "month",
                "year": 2026,
                "period_value": 8,
                "scope": "all",
                "root_department_id": ROOT_ID,
            },
        )
        self.assertEqual(selection.status_code, 200)
        body = selection.json()["snapshot"]
        self.assertEqual(body["provinceAggregatedScore"], 61.86)
        self.assertEqual(body["datasets"][0]["root"]["apiScore"], 7.96)
        self.assertEqual(body["delivery"]["result"], "national-summary")

        rankings = self.client.get(
            "/api/v1/dashboard/province-rankings",
            params={
                "period_type": "month",
                "year": 2026,
                "period_value": 8,
                "scope": "all",
            },
        )
        by_id = {item["rootDepartmentId"]: item for item in rankings.json()}
        self.assertEqual(len(by_id), 2)
        self.assertEqual(by_id[ROOT_ID]["totalScore"], 61.86)
        self.assertEqual(by_id[ROOT_ID]["groups"]["transparency"]["score"], 7.96)
        latest = self.client.get(
            "/api/v1/national-summaries/latest",
            params={
                "period_type": "month",
                "year": 2026,
                "period_value": 8,
            },
        )
        self.assertEqual(latest.status_code, 200)
        self.assertEqual(latest.json()["provinceCount"], 2)
        self.assertEqual(latest.json()["completenessState"], "complete")
        self.assertEqual(latest.json()["groupCount"], 6)
        self.assertEqual(
            set(latest.json()["groupCodes"]),
            {"CKMB", "TDGQ", "CLGQ", "TTTT", "MDHL", "MDSH"},
        )
        listed = self.client.get("/api/v1/national-summaries")
        self.assertEqual(listed.status_code, 200)
        self.assertEqual(listed.json()[0]["completenessState"], "complete")
        self.assertEqual(listed.json()[0]["groupCount"], 6)

    def test_user_cannot_enqueue_aggregate_province_collection(self):
        response = self.client.post(
            "/api/v1/dashboard/requests",
            json={
                "periodType": "year",
                "year": 2026,
                "scope": "all",
                "provinceCode": "01",
            },
        )
        self.assertEqual(response.status_code, 403)
        self.assertIn("hệ thống tự động", response.json()["detail"])
        with self.app.state.session_factory() as session:
            self.assertIsNone(session.scalar(select(CollectionJob)))

    def test_changed_snapshot_is_stored_as_a_new_version_and_latest_is_selected(self):
        with self.app.state.session_factory.begin() as session:
            first = store_normalized_snapshot(session, snapshot_payload())
        changed = copy.deepcopy(snapshot_payload())
        changed["datasets"][0]["raw"]["sha256"] = "b" * 64
        changed["provinceAggregatedScore"] = 6
        changed["datasets"][0]["root"]["apiScore"] = 6
        with self.app.state.session_factory.begin() as session:
            second = store_normalized_snapshot(session, changed)
            self.assertNotEqual(first.id, second.id)
            self.assertEqual(session.scalar(select(func.count()).select_from(Snapshot)), 2)
        latest = self.client.get(
            "/api/v1/snapshots/latest",
            params={
                "root_department_id": ROOT_ID,
                "period_type": "month",
                "year": 2026,
                "period_value": 8,
                "scope": "all",
            },
        )
        self.assertEqual(latest.status_code, 200)
        self.assertEqual(latest.json()["id"], str(second.id))
        dashboard = self.client.get(f"/api/v1/dashboard?root_department_id={ROOT_ID}")
        snapshot = dashboard.json()["snapshots"]["month-2026-08:all"]
        self.assertEqual(snapshot["provinceAggregatedScore"], 6.0)

    def test_incomplete_snapshot_is_rejected(self):
        payload = snapshot_payload()
        payload["status"]["state"] = "incomplete"
        payload["status"]["missingGroups"] = ["dossier-digitized"]
        with self.assertRaises(SnapshotImportError):
            with self.app.state.session_factory.begin() as session:
                store_normalized_snapshot(session, payload)

    def test_formality_relations_come_from_catalog_fields(self):
        payload = {
            "data": {
                "items": [
                    {
                        "id": "019d2bfd-8e22-77ef-819f-e49460350904",
                        "code": "2.000815",
                        "name": "TTHC mẫu",
                        "state": "PUBLISHED",
                        "departmentId": ROOT_ID,
                        "appliedDepartmentIds": [ROOT_ID, CHILD_ID],
                        "publishingDepartmentIds": [ROOT_ID],
                    }
                ]
            }
        }
        with self.app.state.session_factory.begin() as session:
            self.assertEqual(store_formality_page(session, payload), (1, 3))
        response = self.client.get("/api/v1/formalities", params={"code": "2.000815"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()[0]["code"], "2.000815")

    def test_collection_jobs_are_idempotent_and_claimed_by_priority(self):
        first_request = {"period": {"type": "year", "year": 2026}, "scope": "all"}
        urgent_request = {"period": {"type": "quarter", "year": 2026, "quarter": 3}, "scope": "all"}
        department_id = uuid.uuid4()
        formality_id = uuid.uuid4()
        with self.app.state.session_factory.begin() as session:
            session.add(
                Department(
                    id=department_id,
                    name="UBND tỉnh Kiểm thử",
                    attributes={"provinceName": "Tỉnh Kiểm thử"},
                )
            )
            session.add(
                Formality(
                    id=formality_id,
                    code="2.000815",
                    name="Thủ tục kiểm thử hàng đợi",
                    attributes={},
                )
            )
            first, created = enqueue_job(session, first_request, priority=100)
            self.assertTrue(created)
            duplicate, created = enqueue_job(session, first_request, priority=1)
            self.assertFalse(created)
            self.assertEqual(duplicate.id, first.id)
            urgent, created = enqueue_job(session, urgent_request, priority=10)
            self.assertTrue(created)
            detailed, created = enqueue_job(
                session,
                {
                    "period": {"type": "month", "year": 2026, "month": 9},
                    "scope": "formality",
                    "rootDepartmentId": str(department_id),
                    "formalityId": str(formality_id),
                },
                priority=20,
            )
            self.assertTrue(created)

        with self.app.state.session_factory.begin() as session:
            claimed = claim_next_job(session, "worker-test")
            self.assertEqual(claimed.id, urgent.id)
            self.assertEqual(claimed.attempts, 1)
            succeed_job(session, claimed, "worker-test")

        response = self.client.get("/api/v1/collection-jobs")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()), 3)
        succeeded = self.client.get(f"/api/v1/collection-jobs/{urgent.id}")
        self.assertEqual(succeeded.json()["state"], "succeeded")
        enriched = self.client.get(f"/api/v1/collection-jobs/{detailed.id}").json()
        self.assertEqual(enriched["provinceName"], "Tỉnh Kiểm thử")
        self.assertEqual(enriched["formalityCode"], "2.000815")
        self.assertEqual(enriched["formalityName"], "Thủ tục kiểm thử hàng đợi")

    def test_missing_formality_selection_enqueues_once_and_honors_open_circuit(self):
        formality_id = uuid.uuid4()
        with self.app.state.session_factory.begin() as session:
            store_normalized_snapshot(session, snapshot_payload())
            session.add(
                Formality(
                    id=formality_id,
                    code="2.000815",
                    name="Thủ tục kiểm thử",
                    attributes={},
                )
            )
            open_collection_circuit(
                session,
                reason="office-connectivity",
                detail={"safe": True},
            )

        request = {
            "periodType": "month",
            "year": 2026,
            "periodValue": 9,
            "scope": "formality",
            "formalityId": str(formality_id),
        }
        first = self.client.post("/api/v1/dashboard/requests", json=request)
        self.assertEqual(first.status_code, 202)
        self.assertTrue(first.json()["created"])
        self.assertEqual(first.json()["state"], "queued")
        self.assertEqual(first.json()["circuitState"], "open")

        duplicate = self.client.post("/api/v1/dashboard/requests", json=request)
        self.assertEqual(duplicate.status_code, 202)
        self.assertFalse(duplicate.json()["created"])
        self.assertEqual(duplicate.json()["jobId"], first.json()["jobId"])

        blocked = run_one_job(
            self.app.state.session_factory,
            lambda job_id, job_request: snapshot_payload(),
            worker_id="worker-test",
        )
        self.assertEqual(blocked.state, "circuit-open")
        with self.app.state.session_factory() as session:
            jobs = session.scalars(select(CollectionJob)).all()
            self.assertEqual(len(jobs), 1)
            self.assertEqual(jobs[0].state, "queued")

        future = self.client.post(
            "/api/v1/dashboard/requests",
            json={**request, "year": 9999, "periodValue": 1},
        )
        self.assertEqual(future.status_code, 422)

    def test_collection_job_retry_halt_and_lease_ownership(self):
        with self.app.state.session_factory.begin() as session:
            job, _ = enqueue_job(session, {"fixture": "safe"})
        with self.app.state.session_factory.begin() as session:
            claimed = claim_next_job(session, "worker-a")
            with self.assertRaises(JobStateError):
                succeed_job(session, claimed, "worker-b")
            retry_or_fail_job(
                session,
                claimed,
                "worker-a",
                {"kind": "timeout", "retryable": True},
                delay_seconds=0,
            )
        with self.app.state.session_factory.begin() as session:
            claimed = claim_next_job(session, "worker-a")
            self.assertEqual(claimed.attempts, 2)
            halt_job(
                session,
                claimed,
                "worker-a",
                {"kind": "upstream-safety-stop", "retryable": False},
            )
        with self.app.state.session_factory() as session:
            stored = session.get(CollectionJob, job.id)
            self.assertEqual(stored.state, "halted")
            self.assertEqual(stored.error["kind"], "upstream-safety-stop")

    def test_worker_imports_snapshot_and_finishes_job(self):
        with self.app.state.session_factory.begin() as session:
            job, _ = enqueue_job(session, {"fixture": "normalized"})

        result = run_one_job(
            self.app.state.session_factory,
            lambda job_id, request: snapshot_payload(),
            worker_id="worker-test",
        )
        self.assertEqual(result.state, "succeeded")
        with self.app.state.session_factory() as session:
            stored = session.get(CollectionJob, job.id)
            self.assertEqual(stored.state, "succeeded")
            self.assertEqual(session.scalar(select(func.count()).select_from(Snapshot)), 1)

    def test_province_batch_skips_available_and_chains_one_job_at_a_time(self):
        roots = [
            ProvinceRoot("25", "Phú Thọ", uuid.UUID(ROOT_ID), "UBND tỉnh Phú Thọ", "H44", "fixture"),
            ProvinceRoot("80", "Tây Ninh", uuid.UUID(TAY_NINH_ROOT_ID), "UBND tỉnh Tây Ninh", "H70", "fixture"),
            ProvinceRoot("01", "Hà Nội", uuid.UUID(HA_NOI_ROOT_ID), "UBND Thành phố Hà Nội", "H26", "fixture"),
        ]
        with self.app.state.session_factory.begin() as session:
            store_normalized_snapshot(session, snapshot_payload())
            batch, created = create_province_batch(
                session,
                roots,
                PeriodSelection("month", 2026, 8),
                catalog_version="fixture:v1",
            )
            self.assertTrue(created)
            duplicate, created = create_province_batch(
                session,
                roots,
                PeriodSelection("month", 2026, 8),
                catalog_version="fixture:v1",
            )
            self.assertFalse(created)
            self.assertEqual(duplicate.id, batch.id)

        with self.app.state.session_factory() as session:
            stored = session.get(ProvinceCollectionBatch, batch.id)
            states = list(
                session.scalars(
                    select(ProvinceCollectionBatchItem.state)
                    .where(ProvinceCollectionBatchItem.batch_id == batch.id)
                    .order_by(ProvinceCollectionBatchItem.position)
                )
            )
            self.assertEqual(stored.total_items, 3)
            self.assertEqual(stored.available_items, 1)
            self.assertEqual(states.count("skipped"), 1)
            self.assertEqual(states.count("queued"), 1)
            self.assertEqual(states.count("pending"), 1)
            self.assertEqual(session.scalar(select(func.count()).select_from(CollectionJob)), 1)

        def collect(job_id, request):
            root_id = request["rootDepartmentId"]
            root_name = next(
                item.department_name for item in roots if str(item.root_department_id) == root_id
            )
            return snapshot_payload(root_id=root_id, root_name=root_name)

        first = run_one_job(
            self.app.state.session_factory,
            collect,
            worker_id="province-worker",
        )
        self.assertEqual(first.state, "succeeded")
        with self.app.state.session_factory() as session:
            stored = session.get(ProvinceCollectionBatch, batch.id)
            self.assertEqual(stored.completed_items, 1)
            self.assertEqual(stored.state, "running")
            self.assertEqual(session.scalar(select(func.count()).select_from(CollectionJob)), 2)

        second = run_one_job(
            self.app.state.session_factory,
            collect,
            worker_id="province-worker",
        )
        self.assertEqual(second.state, "succeeded")
        with self.app.state.session_factory() as session:
            stored = session.get(ProvinceCollectionBatch, batch.id)
            self.assertEqual(stored.completed_items, 2)
            self.assertEqual(stored.available_items, 1)
            self.assertEqual(stored.state, "succeeded")
        response = self.client.get(f"/api/v1/province-batches/{batch.id}")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["state"], "succeeded")
        items = self.client.get(f"/api/v1/province-batches/{batch.id}/items")
        self.assertEqual(items.status_code, 200)
        self.assertEqual(len(items.json()), 3)
        self.assertEqual(
            sorted(item["state"] for item in items.json()),
            ["skipped", "succeeded", "succeeded"],
        )

    def test_province_batch_halts_with_circuit_and_resumes_from_checkpoint(self):
        root = ProvinceRoot(
            "80",
            "Tây Ninh",
            uuid.UUID(TAY_NINH_ROOT_ID),
            "UBND tỉnh Tây Ninh",
            "H70",
            "fixture",
        )
        with self.app.state.session_factory.begin() as session:
            batch, _ = create_province_batch(
                session,
                [root],
                PeriodSelection("month", 2026, 8),
                catalog_version="fixture:v1",
            )

        def rejected(job_id, request):
            raise SafetyStop("Request Rejected")

        halted = run_one_job(
            self.app.state.session_factory,
            rejected,
            worker_id="province-worker",
        )
        self.assertEqual(halted.state, "halted")
        with self.app.state.session_factory.begin() as session:
            stored = session.get(ProvinceCollectionBatch, batch.id)
            item = session.scalar(
                select(ProvinceCollectionBatchItem).where(
                    ProvinceCollectionBatchItem.batch_id == batch.id
                )
            )
            control = session.get(CollectionControl, "dvcqg")
            self.assertEqual(stored.state, "halted")
            self.assertEqual(item.state, "halted")
            self.assertEqual(control.circuit_state, "open")
            close_collection_circuit(session)
            resume_province_batch(session, stored)

        resumed = run_one_job(
            self.app.state.session_factory,
            lambda job_id, request: snapshot_payload(
                root_id=request["rootDepartmentId"],
                root_name=root.department_name,
            ),
            worker_id="province-worker",
        )
        self.assertEqual(resumed.state, "succeeded")
        with self.app.state.session_factory() as session:
            stored = session.get(ProvinceCollectionBatch, batch.id)
            self.assertEqual(stored.state, "succeeded")
            self.assertEqual(stored.failed_items, 0)
            self.assertEqual(stored.completed_items, 1)

    def test_named_province_refresh_does_not_skip_existing_snapshot(self):
        root = ProvinceRoot(
            "25",
            "Phú Thọ",
            uuid.UUID(ROOT_ID),
            "UBND tỉnh Phú Thọ",
            "H44",
            "fixture",
        )
        with self.app.state.session_factory.begin() as session:
            store_normalized_snapshot(session, snapshot_payload())
            batch, created = create_province_batch(
                session,
                [root],
                PeriodSelection("month", 2026, 8),
                catalog_version="fixture:v1",
                refresh_key="2026-10-02",
            )
            self.assertTrue(created)
            self.assertEqual(batch.available_items, 0)
        with self.app.state.session_factory() as session:
            item = session.scalar(
                select(ProvinceCollectionBatchItem).where(
                    ProvinceCollectionBatchItem.batch_id == batch.id
                )
            )
            self.assertEqual(item.state, "queued")

    def test_detail_refresh_rotates_current_year_month_and_quarter(self):
        now = datetime(2026, 10, 2, 2, 15, tzinfo=timezone.utc)
        year = choose_detail_refresh_period(now, {})
        self.assertEqual(year, PeriodSelection("year", 2026))
        month = choose_detail_refresh_period(
            now,
            {("year", 2026, None): now},
        )
        self.assertEqual(month, PeriodSelection("month", 2026, 10))
        quarter = choose_detail_refresh_period(
            now,
            {
                ("year", 2026, None): now,
                ("month", 2026, 10): now,
            },
        )
        self.assertEqual(quarter, PeriodSelection("quarter", 2026, 4))
        fresh = choose_detail_refresh_period(
            now,
            {
                ("year", 2026, None): now,
                ("month", 2026, 10): now,
                ("quarter", 2026, 4): now,
            },
        )
        self.assertIsNone(fresh)

    def test_automatic_refresh_reuses_only_fresh_provinces(self):
        now = datetime(2026, 10, 2, 9, 0, tzinfo=timezone.utc)
        roots = [
            ProvinceRoot("25", "Phú Thọ", uuid.UUID(ROOT_ID), "UBND tỉnh Phú Thọ", "H44", "fixture"),
            ProvinceRoot("80", "Tây Ninh", uuid.UUID(TAY_NINH_ROOT_ID), "UBND tỉnh Tây Ninh", "H72", "fixture"),
        ]
        with self.app.state.session_factory.begin() as session:
            store_normalized_snapshot(session, snapshot_payload())
            store_normalized_snapshot(session, snapshot_payload(
                root_id=TAY_NINH_ROOT_ID, root_name="UBND tỉnh Tây Ninh",
                child_id=TAY_NINH_CHILD_ID,
            ))
            snapshots = list(session.scalars(select(Snapshot)))
            for snapshot in snapshots:
                snapshot.created_at = now - timedelta(
                    hours=73 if str(snapshot.root_department_id) == ROOT_ID else 1
                )
            session.flush()
            batch, _ = create_province_batch(
                session, roots, PeriodSelection("month", 2026, 8),
                catalog_version="fixture:freshness", refresh_key="auto-test",
                fresh_after=now - timedelta(hours=72),
            )
            self.assertEqual(batch.available_items, 1)
            items = list(session.scalars(select(ProvinceCollectionBatchItem).where(
                ProvinceCollectionBatchItem.batch_id == batch.id
            )))
            by_root = {str(item.root_department_id): item.state for item in items}
            self.assertEqual(by_root[ROOT_ID], "queued")
            self.assertEqual(by_root[TAY_NINH_ROOT_ID], "skipped")

    def test_worker_halts_on_upstream_safety_signal(self):
        with self.app.state.session_factory.begin() as session:
            job, _ = enqueue_job(session, {"fixture": "rejected"}, priority=1)
            queued, _ = enqueue_job(session, {"fixture": "must-wait"}, priority=100)

        def rejected(job_id, request):
            raise SafetyStop("Request Rejected")

        result = run_one_job(
            self.app.state.session_factory,
            rejected,
            worker_id="worker-test",
        )
        self.assertEqual(result.state, "halted")
        with self.app.state.session_factory() as session:
            stored = session.get(CollectionJob, job.id)
            self.assertEqual(stored.state, "halted")
            self.assertEqual(stored.error["kind"], "upstream-safety-stop")
            control = session.get(CollectionControl, "dvcqg")
            self.assertEqual(control.circuit_state, "open")

        blocked = run_one_job(
            self.app.state.session_factory,
            lambda job_id, request: snapshot_payload(),
            worker_id="worker-other",
        )
        self.assertEqual(blocked.state, "circuit-open")
        with self.app.state.session_factory() as session:
            self.assertEqual(session.get(CollectionJob, queued.id).state, "queued")

        with self.app.state.session_factory.begin() as session:
            close_collection_circuit(session)
        resumed = run_one_job(
            self.app.state.session_factory,
            lambda job_id, request: snapshot_payload(),
            worker_id="worker-other",
        )
        self.assertEqual(resumed.state, "succeeded")


if __name__ == "__main__":
    unittest.main()
