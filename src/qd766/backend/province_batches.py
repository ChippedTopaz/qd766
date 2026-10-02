from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime
from collections.abc import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from qd766.periods import PeriodSelection
from qd766.province_roots import ProvinceRoot

from .jobs import enqueue_job
from .models import (
    CollectionJob,
    Department,
    ProvinceCollectionBatch,
    ProvinceCollectionBatchItem,
    Snapshot,
)


def create_province_batch(
    session: Session,
    roots: Iterable[ProvinceRoot],
    period: PeriodSelection,
    *,
    catalog_version: str,
    refresh_key: str | None = None,
    fresh_after: datetime | None = None,
) -> tuple[ProvinceCollectionBatch, bool]:
    """Create one resumable national batch and enqueue only its first missing province."""
    period.validate_collectable()
    ordered = sorted(roots, key=lambda item: item.province_code)
    if not ordered:
        raise ValueError("Province catalog is empty")
    if len({item.province_code for item in ordered}) != len(ordered):
        raise ValueError("Province catalog contains duplicate province codes")
    if len({item.root_department_id for item in ordered}) != len(ordered):
        raise ValueError("Province catalog contains duplicate root departments")

    identity = {
        "kind": "province-batch",
        "periodType": period.type,
        "year": period.year,
        "periodValue": period.value,
        "catalogVersion": catalog_version,
        "rootDepartmentIds": [str(item.root_department_id) for item in ordered],
    }
    if refresh_key is not None:
        identity["refreshKey"] = refresh_key
    if fresh_after is not None:
        identity["freshAfter"] = fresh_after.isoformat()
    canonical = json.dumps(identity, sort_keys=True, separators=(",", ":")).encode()
    key = "province-batch:v1:" + hashlib.sha256(canonical).hexdigest()
    existing = session.scalar(
        select(ProvinceCollectionBatch).where(
            ProvinceCollectionBatch.idempotency_key == key
        )
    )
    if existing is not None:
        return existing, False

    for root in ordered:
        department = session.get(Department, root.root_department_id)
        if department is None:
            session.add(
                Department(
                    id=root.root_department_id,
                    code=root.department_code or None,
                    name=root.department_name,
                    department_type="PROVINCE",
                    department_level="PROVINCE_TOTAL",
                    agency_level="level_1",
                    attributes={
                        "provinceCode": root.province_code,
                        "provinceName": root.province_name,
                        "catalogSource": root.source,
                    },
                )
            )
    session.flush()

    available_statement = select(Snapshot.root_department_id).where(
        Snapshot.state == "complete",
        Snapshot.scope == "all",
        Snapshot.period_type == period.type,
        Snapshot.year == period.year,
    )
    available_statement = (
        available_statement.where(Snapshot.period_value.is_(None))
        if period.value is None
        else available_statement.where(Snapshot.period_value == period.value)
    )
    # A named refresh deliberately creates new immutable versions. Without a
    # refresh key, the original backfill behavior remains: existing snapshots
    # are skipped.
    if fresh_after is not None:
        available_statement = available_statement.where(Snapshot.created_at > fresh_after)
        available = set(session.scalars(available_statement))
    else:
        available = (
            set() if refresh_key is not None else set(session.scalars(available_statement))
        )
    batch = ProvinceCollectionBatch(
        idempotency_key=key,
        state="queued",
        period_type=period.type,
        year=period.year,
        period_value=period.value,
        catalog_version=catalog_version,
        total_items=len(ordered),
        available_items=sum(root.root_department_id in available for root in ordered),
        completed_items=0,
        failed_items=0,
    )
    session.add(batch)
    session.flush()
    for position, root in enumerate(ordered):
        session.add(
            ProvinceCollectionBatchItem(
                batch_id=batch.id,
                position=position,
                province_code=root.province_code,
                province_name=root.province_name,
                root_department_id=root.root_department_id,
                state="skipped" if root.root_department_id in available else "pending",
            )
        )
    session.flush()
    enqueue_next_province_batch_item(session, batch)
    return batch, True


def enqueue_next_province_batch_item(
    session: Session,
    batch: ProvinceCollectionBatch,
) -> CollectionJob | None:
    item = session.scalar(
        select(ProvinceCollectionBatchItem)
        .where(
            ProvinceCollectionBatchItem.batch_id == batch.id,
            ProvinceCollectionBatchItem.state == "pending",
        )
        .order_by(ProvinceCollectionBatchItem.position)
        .with_for_update(skip_locked=True)
        .limit(1)
    )
    if item is None:
        batch.state = "failed" if batch.failed_items else "succeeded"
        session.flush()
        return None

    period: dict[str, object] = {"type": batch.period_type, "year": batch.year}
    if batch.period_type in {"month", "quarter"}:
        period[batch.period_type] = batch.period_value
    request = {
        "kind": "evaluation-snapshot",
        "rootDepartmentId": str(item.root_department_id),
        "period": period,
        "scope": "all",
        "provinceBatchId": str(batch.id),
        "provinceBatchItemId": item.id,
    }
    job, _ = enqueue_job(
        session,
        request,
        priority=55,
        idempotency_key=f"province-batch:v1:{batch.id}:{item.id}",
    )
    if job.state in {"failed", "halted"}:
        job.state = "queued"
        job.attempts = 0
        job.next_run_at = None
        job.locked_at = None
        job.locked_by = None
        job.error = None
    item.state = "queued"
    item.job_id = job.id
    if batch.state != "running":
        batch.state = "queued"
    session.flush()
    return job


def mark_province_batch_job_running(session: Session, job: CollectionJob) -> None:
    ids = _province_batch_ids(job)
    if ids is None:
        return
    batch, item = _locked_batch_item(session, *ids)
    item.state = "running"
    batch.state = "running"
    session.flush()


def finish_province_batch_job(
    session: Session,
    job: CollectionJob,
    state: str,
    error: dict | None = None,
) -> None:
    ids = _province_batch_ids(job)
    if ids is None:
        return
    batch, item = _locked_batch_item(session, *ids)
    if item.state in {"succeeded", "failed", "halted"}:
        return
    item.state = state
    item.error = error
    if state == "succeeded":
        batch.completed_items += 1
        enqueue_next_province_batch_item(session, batch)
    else:
        batch.failed_items += 1
        batch.state = state
        batch.error = error
    session.flush()


def resume_province_batch(
    session: Session,
    batch: ProvinceCollectionBatch,
) -> CollectionJob | None:
    item = session.scalar(
        select(ProvinceCollectionBatchItem)
        .where(
            ProvinceCollectionBatchItem.batch_id == batch.id,
            ProvinceCollectionBatchItem.state.in_(["failed", "halted"]),
        )
        .order_by(ProvinceCollectionBatchItem.position)
        .with_for_update()
        .limit(1)
    )
    if item is not None:
        item.state = "pending"
        item.error = None
        item.job_id = None
        batch.failed_items = max(0, batch.failed_items - 1)
    batch.state = "queued"
    batch.error = None
    session.flush()
    return enqueue_next_province_batch_item(session, batch)


def _province_batch_ids(job: CollectionJob) -> tuple[uuid.UUID, int] | None:
    batch_value = job.request.get("provinceBatchId")
    item_value = job.request.get("provinceBatchItemId")
    if batch_value is None and item_value is None:
        return None
    if batch_value is None or item_value is None:
        raise ValueError("Incomplete province batch job reference")
    return uuid.UUID(str(batch_value)), int(item_value)


def _locked_batch_item(
    session: Session,
    batch_id: uuid.UUID,
    item_id: int,
) -> tuple[ProvinceCollectionBatch, ProvinceCollectionBatchItem]:
    batch = session.get(ProvinceCollectionBatch, batch_id)
    item = session.get(ProvinceCollectionBatchItem, item_id)
    if batch is None or item is None or item.batch_id != batch.id:
        raise ValueError("Province batch job references an unknown batch item")
    return batch, item
