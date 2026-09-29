import sys
import unittest
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from fastapi.testclient import TestClient

from qd766.backend import create_app
from qd766.backend.batches import finish_batch_job, mark_batch_job_running
from qd766.backend.config import Settings
from qd766.backend.jobs import claim_next_job, succeed_job
from qd766.backend.models import (
    Base,
    CollectionBatch,
    CollectionBatchItem,
    CollectionJob,
    Department,
    Formality,
    Snapshot,
)
from sqlalchemy import select
from qd766.province_catalog import AmSieuTocCatalogClient


INDEX = [
    {
        "id": "00000000-0000-0000-0000-000000000001", "ma_tthc": "1.000001", "ten_tthc": "Dùng chung hai cấp",
        "cap_thuc_hien": "Cấp tỉnh, Cấp xã", "linh_vuc": "Hộ tịch",
        "co_quan_cong_bo": "Bộ Tư pháp", "nganh_doc": False,
        "loai_tthc": "TTHC Tiêu chuẩn", "state": "ACTIVE",
    },
    {
        "id": "00000000-0000-0000-0000-000000000002", "ma_tthc": "1.000002", "ten_tthc": "Của Phú Thọ",
        "cap_thuc_hien": "Cấp tỉnh", "linh_vuc": "Đất đai",
        "co_quan_cong_bo": "Ủy ban nhân dân tỉnh Phú Thọ", "nganh_doc": True,
        "loai_tthc": "TTHC Tiêu chuẩn", "state": "ACTIVE",
    },
    {
        "id": "00000000-0000-0000-0000-000000000003", "ma_tthc": "1.000003", "ten_tthc": "Tỉnh khác",
        "cap_thuc_hien": "Cấp xã", "linh_vuc": "Hộ tịch",
        "co_quan_cong_bo": "UBND tỉnh Hà Nội", "nganh_doc": False,
    },
    {
        "id": "00000000-0000-0000-0000-000000000004", "ma_tthc": "1.000004", "ten_tthc": "Ngành dọc bị loại",
        "cap_thuc_hien": "Cấp tỉnh", "linh_vuc": "Công an",
        "co_quan_cong_bo": "Bộ Công an", "nganh_doc": False,
    },
    {
        "id": "00000000-0000-0000-0000-000000000005", "ma_tthc": "1.000005", "ten_tthc": "Whitelist thắng blacklist",
        "cap_thuc_hien": "Cấp xã", "linh_vuc": "Công an đặc biệt",
        "co_quan_cong_bo": "Bộ Công an", "nganh_doc": True,
    },
    {
        "id": "00000000-0000-0000-0000-000000000006", "ma_tthc": "1.000006", "ten_tthc": "Chỉ cấp bộ",
        "cap_thuc_hien": "Cấp Bộ", "linh_vuc": "Tư pháp",
        "co_quan_cong_bo": "Bộ Tư pháp", "nganh_doc": False,
    },
    {
        "id": "00000000-0000-0000-0000-000000000007", "ma_tthc": "1.000007", "ten_tthc": "Nội bộ cấp xã",
        "cap_thuc_hien": "Cấp xã", "linh_vuc": "Tư pháp",
        "co_quan_cong_bo": "Bộ Tư pháp", "nganh_doc": False,
        "loai_tthc": "TTHC Nội bộ", "state": "ACTIVE",
    },
]

RULES = {
    "whitelist_codes": ["1.000005"],
    "whitelist_domains": [],
    "banned_codes": [],
    "banned_domains": [{"linh_vuc": "Công an", "co_quan_cong_bo": "Bộ Công an"}],
}


def fixture_fetcher(url):
    if url.endswith("index.json"):
        return INDEX
    if url.endswith("version.json"):
        return {"last_updated": "2026-09-28T15:47:15.297Z", "total_records": 7}
    if url.endswith("isVertical.json"):
        return RULES
    raise AssertionError(f"Unexpected fixture URL: {url}")


class ProvinceCatalogTest(unittest.TestCase):
    def setUp(self):
        self.catalog_client = AmSieuTocCatalogClient(fetch_json=fixture_fetcher)

    def test_statistics_rules_match_am_sieu_toc(self):
        catalog = self.catalog_client.load("25", include_internal=True)
        self.assertEqual(
            [item.code for item in catalog.select()],
            ["1.000001", "1.000002", "1.000005", "1.000007"],
        )
        self.assertEqual(catalog.total_count, 4)
        self.assertEqual(catalog.province_count, 2)
        self.assertEqual(catalog.ward_count, 3)
        whitelisted = next(item for item in catalog.formalities if item.code == "1.000005")
        self.assertFalse(whitelisted.is_vertical)

    def test_internal_toggle(self):
        catalog = self.catalog_client.load("25", include_internal=False)
        self.assertEqual(catalog.total_count, 3)
        self.assertNotIn("1.000007", [item.code for item in catalog.formalities])

    def test_field_level_and_text_filters(self):
        catalog = self.catalog_client.load("25")
        self.assertEqual(
            [item.code for item in catalog.select(level="ward", field="Hộ tịch")],
            ["1.000001"],
        )
        self.assertEqual(
            [item.code for item in catalog.select(query="whitelist")],
            ["1.000005"],
        )

    def test_api_exposes_counts_and_level_selection(self):
        app = create_app(Settings(database_url="sqlite+pysqlite://"))
        Base.metadata.create_all(app.state.engine)
        app.state.province_catalog_client = self.catalog_client
        root_id = uuid.UUID("10000000-0000-0000-0000-000000000001")
        with app.state.session_factory() as session:
            session.add(Department(id=root_id, code="25", name="UBND tỉnh Phú Thọ"))
            session.add(Snapshot(
                snapshot_key="fixture-root",
                schema_version=1,
                root_department_id=root_id,
                period_type="month",
                year=2026,
                period_value=8,
                scope="all",
                formality_id=None,
                state="complete",
                policy={},
                status_detail={},
            ))
            session.commit()
        client = TestClient(app)
        try:
            response = client.get(
                "/api/v1/province-catalog/25",
                params={"level": "ward", "include_internal": "false", "limit": 10},
            )
            self.assertEqual(response.status_code, 200)
            payload = response.json()
            self.assertEqual(payload["selection"]["formalityCount"], 2)
            self.assertEqual(payload["selection"]["totalCount"], 3)
            self.assertEqual(payload["selection"]["provinceCount"], 2)
            self.assertEqual(payload["selection"]["wardCount"], 2)
            self.assertEqual(
                [item["code"] for item in payload["items"]],
                ["1.000001", "1.000005"],
            )
            self.assertEqual(response.headers["X-QD766-Catalog-Cache"], "miss")

            preview = client.get(
                "/api/v1/province-catalog/25/preview",
                params={
                    "period_type": "month",
                    "year": 2026,
                    "period_value": 9,
                    "level": "ward",
                    "q": "whitelist",
                },
            )
            self.assertEqual(preview.status_code, 200)
            self.assertEqual(preview.json()["counts"], {
                "selected": 1,
                "available": 0,
                "missing": 1,
            })
            self.assertEqual(preview.json()["items"][0]["code"], "1.000005")

            formality_id = "00000000-0000-0000-0000-000000000005"
            queued = client.post("/api/v1/dashboard/requests", json={
                "periodType": "month",
                "year": 2026,
                "periodValue": 9,
                "scope": "formality",
                "formalityId": formality_id,
                "provinceCode": "25",
                "formalityCode": "1.000005",
            })
            self.assertEqual(queued.status_code, 202)
            self.assertTrue(queued.json()["created"])
            with app.state.session_factory() as session:
                stored = session.get(Formality, uuid.UUID(formality_id))
                self.assertIsNotNone(stored)
                self.assertEqual(stored.name, "Whitelist thắng blacklist")

            batch_response = client.post("/api/v1/formality-batches", json={
                "provinceCode": "25",
                "periodType": "month",
                "year": 2026,
                "periodValue": 9,
                "level": "ward",
                "includeInternal": True,
            })
            self.assertEqual(batch_response.status_code, 202)
            batch_payload = batch_response.json()
            self.assertEqual(batch_payload["totalItems"], 3)
            batch_id = uuid.UUID(batch_payload["id"])
            duplicate = client.post("/api/v1/formality-batches", json={
                "provinceCode": "25",
                "periodType": "month",
                "year": 2026,
                "periodValue": 9,
                "level": "ward",
                "includeInternal": True,
            })
            self.assertEqual(duplicate.json()["id"], str(batch_id))

            with app.state.session_factory.begin() as session:
                items = list(session.scalars(
                    select(CollectionBatchItem)
                    .where(CollectionBatchItem.batch_id == batch_id)
                    .order_by(CollectionBatchItem.position)
                ))
                self.assertEqual([item.state for item in items], ["queued", "pending", "pending"])
                batch_jobs = [
                    job
                    for job in session.scalars(select(CollectionJob))
                    if job.request.get("batchId") == str(batch_id)
                ]
                self.assertEqual(len(batch_jobs), 1)
                claimed = claim_next_job(session, "batch-worker")
                # The earlier single-TTHC request has higher priority (50). Finish it
                # first so the batch's priority-60 child can be claimed next.
                if claimed.request.get("batchId") is None:
                    succeed_job(session, claimed, "batch-worker")
                    claimed = claim_next_job(session, "batch-worker")
                mark_batch_job_running(session, claimed)
                succeed_job(session, claimed, "batch-worker")
                finish_batch_job(session, claimed, "succeeded")

            with app.state.session_factory() as session:
                batch = session.get(CollectionBatch, batch_id)
                self.assertEqual(batch.completed_items, 1)
                items = list(session.scalars(
                    select(CollectionBatchItem)
                    .where(CollectionBatchItem.batch_id == batch_id)
                    .order_by(CollectionBatchItem.position)
                ))
                self.assertEqual([item.state for item in items], ["succeeded", "queued", "pending"])
        finally:
            Base.metadata.drop_all(app.state.engine)
            app.state.engine.dispose()


if __name__ == "__main__":
    unittest.main()
