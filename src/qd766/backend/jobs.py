from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .models import CollectionJob


class JobStateError(RuntimeError):
    pass


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def request_idempotency_key(request: dict[str, Any]) -> str:
    canonical = json.dumps(
        request,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return "collection:v1:" + hashlib.sha256(canonical).hexdigest()


def enqueue_job(
    session: Session,
    request: dict[str, Any],
    *,
    priority: int = 100,
    idempotency_key: str | None = None,
) -> tuple[CollectionJob, bool]:
    key = idempotency_key or request_idempotency_key(request)
    existing = session.scalar(
        select(CollectionJob).where(CollectionJob.idempotency_key == key)
    )
    if existing is not None:
        return existing, False

    job = CollectionJob(
        idempotency_key=key,
        state="queued",
        priority=priority,
        request=request,
        attempts=0,
    )
    try:
        with session.begin_nested():
            session.add(job)
            session.flush()
    except IntegrityError:
        # A concurrent producer won the unique-key race. The savepoint keeps the
        # caller's transaction usable, and both producers receive the same job.
        existing = session.scalar(
            select(CollectionJob).where(CollectionJob.idempotency_key == key)
        )
        if existing is None:
            raise
        return existing, False
    return job, True


def claim_next_job(
    session: Session,
    worker_id: str,
    *,
    now: datetime | None = None,
) -> CollectionJob | None:
    claimed_at = now or utc_now()
    statement = (
        select(CollectionJob)
        .where(
            CollectionJob.state == "queued",
            or_(
                CollectionJob.next_run_at.is_(None),
                CollectionJob.next_run_at <= claimed_at,
            ),
        )
        .order_by(
            CollectionJob.priority.asc(),
            CollectionJob.created_at.asc(),
            CollectionJob.id.asc(),
        )
        .with_for_update(skip_locked=True)
        .limit(1)
    )
    job = session.scalar(statement)
    if job is None:
        return None
    job.state = "running"
    job.attempts += 1
    job.locked_at = claimed_at
    job.locked_by = worker_id
    job.next_run_at = None
    job.error = None
    session.flush()
    return job


def requeue_expired_jobs(
    session: Session,
    *,
    lease_seconds: int,
    now: datetime | None = None,
) -> int:
    current = now or utc_now()
    expired_before = current - timedelta(seconds=lease_seconds)
    jobs = list(
        session.scalars(
            select(CollectionJob)
            .where(
                CollectionJob.state == "running",
                CollectionJob.locked_at < expired_before,
            )
            .with_for_update(skip_locked=True)
        )
    )
    for job in jobs:
        job.state = "queued"
        job.next_run_at = current
        job.locked_at = None
        job.locked_by = None
        job.error = {"kind": "lease-expired", "retryable": True}
    session.flush()
    return len(jobs)


def succeed_job(session: Session, job: CollectionJob, worker_id: str) -> None:
    _require_owner(job, worker_id)
    job.state = "succeeded"
    job.locked_at = None
    job.locked_by = None
    job.next_run_at = None
    job.error = None
    session.flush()


def retry_or_fail_job(
    session: Session,
    job: CollectionJob,
    worker_id: str,
    error: dict[str, Any],
    *,
    max_attempts: int = 3,
    delay_seconds: int = 60,
    now: datetime | None = None,
) -> None:
    _require_owner(job, worker_id)
    retryable = bool(error.get("retryable"))
    if retryable and job.attempts < max_attempts:
        job.state = "queued"
        job.next_run_at = (now or utc_now()) + timedelta(seconds=delay_seconds)
    else:
        job.state = "failed"
        job.next_run_at = None
    job.locked_at = None
    job.locked_by = None
    job.error = error
    session.flush()


def halt_job(
    session: Session,
    job: CollectionJob,
    worker_id: str,
    error: dict[str, Any],
) -> None:
    _require_owner(job, worker_id)
    job.state = "halted"
    job.locked_at = None
    job.locked_by = None
    job.next_run_at = None
    job.error = error
    session.flush()


def _require_owner(job: CollectionJob, worker_id: str) -> None:
    if job.state != "running" or job.locked_by != worker_id:
        raise JobStateError("Job is not running under this worker lease")
