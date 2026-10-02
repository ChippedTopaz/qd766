from __future__ import annotations

import copy
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from qd766.collection import (
    CollectionError,
    SafetyStop,
    Transport,
    collect_snapshot,
    plan_evaluation_requests,
)
from qd766.periods import PeriodSelection
from qd766.snapshot import build_collected_snapshot

from .importer import store_normalized_snapshot
from .batches import finish_batch_job, mark_batch_job_running
from .jobs import (
    acquire_collection_lease,
    claim_next_job,
    halt_job,
    open_collection_circuit,
    requeue_expired_jobs,
    release_collection_lease,
    retry_or_fail_job,
    succeed_job,
)
from .models import CollectionJob
from .paid_requests import (
    refund_paid_requests_for_job,
    settle_paid_requests_for_job,
)
from .province_batches import (
    finish_province_batch_job,
    mark_province_batch_job_running,
)

SnapshotProcessor = Callable[[uuid.UUID, dict[str, Any]], dict[str, Any]]


@dataclass(frozen=True)
class WorkerResult:
    job_id: uuid.UUID | None
    state: str


class EvaluationSnapshotProcessor:
    def __init__(
        self,
        *,
        collection_root: Path,
        transport: Transport,
        minimum_delay_seconds: float = 5.0,
        jitter_seconds: float = 1.0,
        max_retries: int = 1,
    ):
        self.collection_root = collection_root
        self.transport = transport
        self.minimum_delay_seconds = minimum_delay_seconds
        self.jitter_seconds = jitter_seconds
        self.max_retries = max_retries

    def __call__(self, job_id: uuid.UUID, request: dict[str, Any]) -> dict[str, Any]:
        if request.get("kind") != "evaluation-snapshot":
            raise ValueError("Unsupported collection job kind")
        root_department_id = str(uuid.UUID(request["rootDepartmentId"]))
        formality_value = request.get("formalityId")
        formality_id = str(uuid.UUID(formality_value)) if formality_value else None
        period_value = request.get("period")
        if not isinstance(period_value, dict):
            raise ValueError("Collection job period is required")
        period_type = period_value.get("type")
        value = period_value.get(period_type) if period_type in {"month", "quarter"} else None
        period = PeriodSelection(period_type, period_value.get("year"), value)
        period.validate_collectable()

        plan = plan_evaluation_requests(period, root_department_id, formality_id)
        output_dir = self.collection_root / str(job_id)
        collect_snapshot(
            plan,
            period=period,
            output_dir=output_dir,
            transport=self.transport,
            minimum_delay_seconds=self.minimum_delay_seconds,
            jitter_seconds=self.jitter_seconds,
            max_retries=self.max_retries,
        )
        return build_collected_snapshot(output_dir).to_dict()


def run_one_job(
    factory: sessionmaker[Session],
    processor: SnapshotProcessor,
    *,
    worker_id: str,
    lease_seconds: int = 1800,
    max_attempts: int = 3,
    retry_delay_seconds: int = 300,
) -> WorkerResult | None:
    with factory.begin() as session:
        lease_state = acquire_collection_lease(
            session,
            worker_id,
            lease_seconds=lease_seconds,
        )
        if lease_state != "acquired":
            return WorkerResult(None, lease_state)
        requeue_expired_jobs(session, lease_seconds=lease_seconds)
        claimed = claim_next_job(session, worker_id)
        if claimed is None:
            release_collection_lease(session, worker_id)
            return None
        mark_batch_job_running(session, claimed)
        mark_province_batch_job_running(session, claimed)
        job_id = claimed.id
        request = copy.deepcopy(claimed.request)

    try:
        snapshot = processor(job_id, request)
        with factory.begin() as session:
            job = _locked_job(session, job_id)
            stored_snapshot = store_normalized_snapshot(session, snapshot)
            settle_paid_requests_for_job(session, job, stored_snapshot)
            succeed_job(session, job, worker_id)
            finish_batch_job(session, job, "succeeded")
            finish_province_batch_job(session, job, "succeeded")
            release_collection_lease(session, worker_id)
        return WorkerResult(job_id, "succeeded")
    except SafetyStop as error:
        _halt(
            factory,
            job_id,
            worker_id,
            "upstream-safety-stop",
            error,
            open_circuit=True,
        )
        return WorkerResult(job_id, "halted")
    except (ValueError, KeyError, TypeError) as error:
        _halt(factory, job_id, worker_id, "invalid-job-or-data", error)
        return WorkerResult(job_id, "halted")
    except CollectionError as error:
        state = _retry_or_fail(
            factory,
            job_id,
            worker_id,
            "collection-failure",
            error,
            max_attempts=max_attempts,
            retry_delay_seconds=retry_delay_seconds,
        )
        return WorkerResult(job_id, state)
    except Exception as error:
        state = _retry_or_fail(
            factory,
            job_id,
            worker_id,
            "unexpected-worker-failure",
            error,
            max_attempts=max_attempts,
            retry_delay_seconds=retry_delay_seconds,
        )
        return WorkerResult(job_id, state)


def _locked_job(session: Session, job_id: uuid.UUID) -> CollectionJob:
    job = session.scalar(
        select(CollectionJob)
        .where(CollectionJob.id == job_id)
        .with_for_update()
    )
    if job is None:
        raise RuntimeError("Claimed collection job disappeared")
    return job


def _error(kind: str, error: Exception, *, retryable: bool) -> dict[str, Any]:
    return {
        "kind": kind,
        "retryable": retryable,
        "message": str(error)[:500],
    }


def _halt(
    factory: sessionmaker[Session],
    job_id: uuid.UUID,
    worker_id: str,
    kind: str,
    error: Exception,
    *,
    open_circuit: bool = False,
) -> None:
    with factory.begin() as session:
        detail = _error(kind, error, retryable=False)
        job = _locked_job(session, job_id)
        halt_job(session, job, worker_id, detail)
        refund_paid_requests_for_job(session, job, detail)
        finish_batch_job(session, job, "halted", detail)
        finish_province_batch_job(session, job, "halted", detail)
        if open_circuit:
            open_collection_circuit(session, reason=kind, detail=detail)
        else:
            release_collection_lease(session, worker_id)


def _retry_or_fail(
    factory: sessionmaker[Session],
    job_id: uuid.UUID,
    worker_id: str,
    kind: str,
    error: Exception,
    *,
    max_attempts: int,
    retry_delay_seconds: int,
) -> str:
    with factory.begin() as session:
        job = _locked_job(session, job_id)
        retry_or_fail_job(
            session,
            job,
            worker_id,
            _error(kind, error, retryable=True),
            max_attempts=max_attempts,
            delay_seconds=retry_delay_seconds,
        )
        if job.state == "failed":
            refund_paid_requests_for_job(session, job, job.error or {})
            finish_batch_job(session, job, "failed", job.error)
            finish_province_batch_job(session, job, "failed", job.error)
        release_collection_lease(session, worker_id)
        return job.state
