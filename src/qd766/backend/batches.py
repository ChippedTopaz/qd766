from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import CollectionBatch, CollectionBatchItem, CollectionJob


def enqueue_next_batch_item(
    session: Session,
    batch: CollectionBatch,
) -> CollectionJob | None:
    item = session.scalar(
        select(CollectionBatchItem)
        .where(
            CollectionBatchItem.batch_id == batch.id,
            CollectionBatchItem.state == "pending",
        )
        .order_by(CollectionBatchItem.position)
        .with_for_update(skip_locked=True)
        .limit(1)
    )
    if item is None:
        if batch.failed_items:
            batch.state = "failed"
        else:
            batch.state = "succeeded"
        session.flush()
        return None

    from .jobs import enqueue_job

    period: dict[str, object] = {"type": batch.period_type, "year": batch.year}
    if batch.period_type in {"month", "quarter"}:
        period[batch.period_type] = batch.period_value
    request = {
        "kind": "evaluation-snapshot",
        "rootDepartmentId": str(batch.root_department_id),
        "period": period,
        "scope": "formality",
        "formalityId": str(item.formality_id),
        "batchId": str(batch.id),
        "batchItemId": item.id,
    }
    job, _ = enqueue_job(
        session,
        request,
        priority=60,
        idempotency_key=f"batch:v1:{batch.id}:{item.id}",
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


def mark_batch_job_running(session: Session, job: CollectionJob) -> None:
    ids = _batch_ids(job)
    if ids is None:
        return
    batch_id, item_id = ids
    batch = session.get(CollectionBatch, batch_id)
    item = session.get(CollectionBatchItem, item_id)
    if batch is None or item is None or item.batch_id != batch.id:
        raise ValueError("Batch job references an unknown batch item")
    item.state = "running"
    batch.state = "running"
    session.flush()


def finish_batch_job(
    session: Session,
    job: CollectionJob,
    state: str,
    error: dict | None = None,
) -> None:
    ids = _batch_ids(job)
    if ids is None:
        return
    batch_id, item_id = ids
    batch = session.get(CollectionBatch, batch_id)
    item = session.get(CollectionBatchItem, item_id)
    if batch is None or item is None or item.batch_id != batch.id:
        raise ValueError("Batch job references an unknown batch item")
    if item.state in {"succeeded", "failed", "halted"}:
        return
    item.state = state
    item.error = error
    if state == "succeeded":
        batch.completed_items += 1
        enqueue_next_batch_item(session, batch)
    else:
        batch.failed_items += 1
        batch.state = state
        batch.error = error
    session.flush()


def resume_batch(session: Session, batch: CollectionBatch) -> CollectionJob | None:
    item = session.scalar(
        select(CollectionBatchItem)
        .where(
            CollectionBatchItem.batch_id == batch.id,
            CollectionBatchItem.state.in_(["failed", "halted"]),
        )
        .order_by(CollectionBatchItem.position)
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
    return enqueue_next_batch_item(session, batch)


def _batch_ids(job: CollectionJob) -> tuple[uuid.UUID, int] | None:
    batch_value = job.request.get("batchId")
    item_value = job.request.get("batchItemId")
    if batch_value is None and item_value is None:
        return None
    if batch_value is None or item_value is None:
        raise ValueError("Incomplete batch job reference")
    return uuid.UUID(str(batch_value)), int(item_value)
