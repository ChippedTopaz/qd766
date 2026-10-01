#!/usr/bin/env python3
"""Create and inspect sequential national province collection batches."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import uuid
from pathlib import Path

from sqlalchemy import func, select

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from qd766.backend.config import Settings, load_environment_file
from qd766.backend.database import create_database_engine, create_session_factory
from qd766.backend.models import (
    CollectionControl,
    ProvinceCollectionBatch,
    ProvinceCollectionBatchItem,
)
from qd766.backend.province_batches import create_province_batch, resume_province_batch
from qd766.periods import PeriodSelection
from qd766.province_roots import catalog_path, load_province_roots


def _catalog_version() -> str:
    path = catalog_path()
    raw = path.read_bytes()
    payload = json.loads(raw)
    generated = str(payload.get("generatedAt") or "unknown")
    return f"{generated}:{hashlib.sha256(raw).hexdigest()}"


def _payload(session, batch: ProvinceCollectionBatch, *, created: bool | None = None) -> dict:
    counts = dict(
        session.execute(
            select(ProvinceCollectionBatchItem.state, func.count())
            .where(ProvinceCollectionBatchItem.batch_id == batch.id)
            .group_by(ProvinceCollectionBatchItem.state)
        ).all()
    )
    current = session.scalar(
        select(ProvinceCollectionBatchItem)
        .where(
            ProvinceCollectionBatchItem.batch_id == batch.id,
            ProvinceCollectionBatchItem.state.in_(["queued", "running", "failed", "halted"]),
        )
        .order_by(ProvinceCollectionBatchItem.position)
        .limit(1)
    )
    result = {
        "id": str(batch.id),
        "state": batch.state,
        "period": {
            "type": batch.period_type,
            "year": batch.year,
            "value": batch.period_value,
        },
        "totalItems": batch.total_items,
        "availableItems": batch.available_items,
        "completedItems": batch.completed_items,
        "failedItems": batch.failed_items,
        "itemStates": counts,
        "currentItem": None if current is None else {
            "provinceCode": current.province_code,
            "provinceName": current.province_name,
            "state": current.state,
            "jobId": str(current.job_id) if current.job_id else None,
        },
        "createdAt": batch.created_at.isoformat() if batch.created_at else None,
        "updatedAt": batch.updated_at.isoformat() if batch.updated_at else None,
    }
    if created is not None:
        result["created"] = created
    return result


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="action", required=True)
    create = subparsers.add_parser("create")
    create.add_argument("--period-type", choices=("month", "quarter", "year"), required=True)
    create.add_argument("--year", type=int, required=True)
    create.add_argument("--period-value", type=int)
    status = subparsers.add_parser("status")
    status.add_argument("--batch-id")
    resume = subparsers.add_parser("resume")
    resume.add_argument("--batch-id", required=True)
    resume.add_argument("--confirm-reviewed", action="store_true")
    arguments = parser.parse_args()

    load_environment_file(ROOT / ".env")
    engine = create_database_engine(Settings.from_env())
    factory = create_session_factory(engine)
    try:
        if arguments.action == "create":
            period = PeriodSelection(arguments.period_type, arguments.year, arguments.period_value)
            with factory.begin() as session:
                batch, created = create_province_batch(
                    session,
                    load_province_roots().values(),
                    period,
                    catalog_version=_catalog_version(),
                )
                output = _payload(session, batch, created=created)
        elif arguments.action == "resume":
            if not arguments.confirm_reviewed:
                parser.error("resume requires --confirm-reviewed")
            batch_id = uuid.UUID(arguments.batch_id)
            with factory.begin() as session:
                batch = session.get(ProvinceCollectionBatch, batch_id)
                if batch is None:
                    parser.error("province batch was not found")
                if batch.state not in {"failed", "halted"}:
                    parser.error("province batch is not resumable")
                control = session.get(CollectionControl, "dvcqg")
                if control is not None and control.circuit_state == "open":
                    parser.error("DVCQG circuit is open")
                resume_province_batch(session, batch)
                output = _payload(session, batch)
        else:
            with factory() as session:
                if arguments.batch_id:
                    batch = session.get(ProvinceCollectionBatch, uuid.UUID(arguments.batch_id))
                else:
                    batch = session.scalar(
                        select(ProvinceCollectionBatch)
                        .order_by(ProvinceCollectionBatch.created_at.desc())
                        .limit(1)
                    )
                if batch is None:
                    print(json.dumps({"state": "not-created"}))
                    return 1
                output = _payload(session, batch)
        print(json.dumps(output, ensure_ascii=False, indent=2))
        return 0
    finally:
        engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
