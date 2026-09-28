from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy import func, select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, selectinload

from .dashboard import dashboard_payload, snapshot_payload
from .database import get_session
from .jobs import enqueue_job
from .models import CollectionControl, CollectionJob, Dataset, Entity, Formality, FormalityDepartment, Snapshot
from .schemas import (
    CollectionControlResponse,
    CollectionJobResponse,
    DatasetResponse,
    DashboardCollectionRequest,
    DashboardCollectionResponse,
    EntityResponse,
    FormalityResponse,
    HealthResponse,
    SnapshotResponse,
)

router = APIRouter(prefix="/api/v1")
DbSession = Annotated[Session, Depends(get_session)]


@router.get("/health/live", response_model=HealthResponse, tags=["health"])
def live() -> HealthResponse:
    return HealthResponse(status="ok")


@router.get("/health/ready", response_model=HealthResponse, tags=["health"])
def ready(session: DbSession, response: Response) -> HealthResponse:
    try:
        session.execute(text("SELECT 1"))
    except SQLAlchemyError:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return HealthResponse(status="unavailable")
    return HealthResponse(status="ok")


@router.get(
    "/collection-jobs",
    response_model=list[CollectionJobResponse],
    tags=["collection-jobs"],
)
def list_collection_jobs(
    session: DbSession,
    state: str | None = Query(
        default=None,
        pattern="^(queued|running|succeeded|failed|halted)$",
    ),
    limit: int = Query(default=50, ge=1, le=200),
) -> list[CollectionJob]:
    statement = select(CollectionJob).order_by(CollectionJob.created_at.desc()).limit(limit)
    if state is not None:
        statement = statement.where(CollectionJob.state == state)
    return list(session.scalars(statement))


@router.get(
    "/collection-jobs/{job_id}",
    response_model=CollectionJobResponse,
    tags=["collection-jobs"],
)
def get_collection_job(job_id: uuid.UUID, session: DbSession) -> CollectionJob:
    job = session.get(CollectionJob, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Collection job not found")
    return job


@router.get(
    "/collection-control",
    response_model=CollectionControlResponse | None,
    tags=["collection-jobs"],
)
def get_collection_control(session: DbSession) -> CollectionControl | None:
    return session.get(CollectionControl, "dvcqg")


@router.get("/system-status", tags=["health"])
def system_status(request: Request, session: DbSession) -> dict:
    control = session.get(CollectionControl, "dvcqg")
    snapshot_count, latest_snapshot_at = session.execute(
        select(func.count(Snapshot.id), func.max(Snapshot.created_at)).where(
            Snapshot.state == "complete"
        )
    ).one()
    cache_stats = request.app.state.dashboard_cache.stats()
    return {
        "databaseStatus": "ok",
        "circuitState": control.circuit_state if control else "closed",
        "circuitReason": control.reason if control else None,
        "snapshotCount": snapshot_count,
        "latestSnapshotAt": latest_snapshot_at,
        "dashboardCache": {
            "ttlSeconds": request.app.state.settings.dashboard_cache_ttl_seconds,
            "entries": cache_stats.entries,
            "inFlight": cache_stats.in_flight,
            "hits": cache_stats.hits,
            "misses": cache_stats.misses,
            "waits": cache_stats.waits,
        },
    }


@router.get("/dashboard", tags=["dashboard"])
def dashboard(
    request: Request,
    response: Response,
    session: DbSession,
    root_department_id: uuid.UUID | None = None,
) -> dict:
    cache_key = str(root_department_id) if root_department_id else "latest"

    def load_dashboard() -> dict:
        resolved_root_id = root_department_id
        if resolved_root_id is None:
            resolved_root_id = session.scalar(
                select(Snapshot.root_department_id)
                .where(Snapshot.state == "complete")
                .order_by(Snapshot.created_at.desc())
                .limit(1)
            )
        if resolved_root_id is None:
            raise HTTPException(status_code=404, detail="No complete snapshots found")
        statement = (
            select(Snapshot)
            .options(
                selectinload(Snapshot.root_department),
                selectinload(Snapshot.datasets)
                .selectinload(Dataset.entities)
                .selectinload(Entity.department),
                selectinload(Snapshot.datasets)
                .selectinload(Dataset.entities)
                .selectinload(Entity.metrics),
            )
            .where(
                Snapshot.state == "complete",
                Snapshot.root_department_id == resolved_root_id,
            )
            .order_by(Snapshot.year.desc(), Snapshot.period_type, Snapshot.period_value.desc())
        )
        snapshots = list(session.scalars(statement).unique())
        if not snapshots:
            raise HTTPException(status_code=404, detail="No complete snapshots found")
        formality_id = next(
            (snapshot.formality_id for snapshot in snapshots if snapshot.formality_id is not None),
            None,
        )
        formality = session.get(Formality, formality_id) if formality_id else None
        return dashboard_payload(snapshots, formality)

    payload, cache_result = request.app.state.dashboard_cache.get_or_load(
        cache_key,
        load_dashboard,
    )
    response.headers["X-QD766-Cache"] = cache_result
    response.headers["Cache-Control"] = "private, max-age=30"
    return payload


@router.get("/dashboard/selection", tags=["dashboard"])
def dashboard_selection(
    request: Request,
    response: Response,
    session: DbSession,
    period_type: str = Query(pattern="^(month|quarter|year)$"),
    year: int = Query(ge=2000, le=2200),
    scope: str = Query(default="all", pattern="^(all|formality)$"),
    period_value: int | None = None,
    formality_id: uuid.UUID | None = None,
    root_department_id: uuid.UUID | None = None,
) -> dict:
    cache_key = ":".join(
        [
            "selection",
            str(root_department_id or "latest"),
            period_type,
            str(year),
            str(period_value or 0),
            scope,
            str(formality_id or "all"),
        ]
    )

    def load_selection() -> dict:
        resolved_root_id = root_department_id
        if resolved_root_id is None:
            resolved_root_id = session.scalar(
                select(Snapshot.root_department_id)
                .where(Snapshot.state == "complete")
                .order_by(Snapshot.created_at.desc())
                .limit(1)
            )
        statement = (
            select(Snapshot)
            .options(
                selectinload(Snapshot.datasets)
                .selectinload(Dataset.entities)
                .selectinload(Entity.department),
                selectinload(Snapshot.datasets)
                .selectinload(Dataset.entities)
                .selectinload(Entity.metrics),
            )
            .where(
                Snapshot.state == "complete",
                Snapshot.root_department_id == resolved_root_id,
                Snapshot.period_type == period_type,
                Snapshot.year == year,
                Snapshot.scope == scope,
            )
            .order_by(Snapshot.created_at.desc())
        )
        statement = (
            statement.where(Snapshot.period_value.is_(None))
            if period_value is None
            else statement.where(Snapshot.period_value == period_value)
        )
        statement = (
            statement.where(Snapshot.formality_id.is_(None))
            if formality_id is None
            else statement.where(Snapshot.formality_id == formality_id)
        )
        selected = session.scalar(statement.limit(1))
        if selected is None:
            raise HTTPException(status_code=404, detail="Snapshot not found")
        item = snapshot_payload(selected)
        return {"metadata": item["delivery"], "snapshot": item}

    payload, cache_result = request.app.state.dashboard_cache.get_or_load(
        cache_key, load_selection
    )
    response.headers["X-QD766-Cache"] = cache_result
    response.headers["Cache-Control"] = "private, max-age=30"
    return payload


@router.post(
    "/dashboard/requests",
    response_model=DashboardCollectionResponse,
    status_code=status.HTTP_202_ACCEPTED,
    tags=["dashboard"],
)
def request_dashboard_collection(
    payload: DashboardCollectionRequest,
    session: DbSession,
) -> DashboardCollectionResponse:
    root_department_id = session.scalar(
        select(Snapshot.root_department_id)
        .where(Snapshot.state == "complete")
        .order_by(Snapshot.created_at.desc())
        .limit(1)
    )
    if root_department_id is None:
        raise HTTPException(status_code=409, detail="No root department is available")
    if payload.formality_id is not None and session.get(Formality, payload.formality_id) is None:
        raise HTTPException(status_code=404, detail="Formality not found")
    control = session.get(CollectionControl, "dvcqg")
    circuit_state = control.circuit_state if control else "closed"

    existing = select(Snapshot.id).where(
        Snapshot.state == "complete",
        Snapshot.root_department_id == root_department_id,
        Snapshot.period_type == payload.period_type,
        Snapshot.year == payload.year,
        Snapshot.scope == payload.scope,
    )
    existing = (
        existing.where(Snapshot.period_value.is_(None))
        if payload.period_value is None
        else existing.where(Snapshot.period_value == payload.period_value)
    )
    existing = (
        existing.where(Snapshot.formality_id.is_(None))
        if payload.formality_id is None
        else existing.where(Snapshot.formality_id == payload.formality_id)
    )
    if session.scalar(existing.limit(1)) is not None:
        return DashboardCollectionResponse(
            job_id=None,
            state="ready",
            created=False,
            circuit_state=circuit_state,
            message="Dữ liệu đã có trong PostgreSQL.",
        )

    period: dict[str, object] = {"type": payload.period_type, "year": payload.year}
    if payload.period_type in {"month", "quarter"}:
        period[payload.period_type] = payload.period_value
    request_value: dict[str, object] = {
        "kind": "evaluation-snapshot",
        "rootDepartmentId": str(root_department_id),
        "period": period,
        "scope": payload.scope,
    }
    if payload.formality_id is not None:
        request_value["formalityId"] = str(payload.formality_id)

    job, created = enqueue_job(session, request_value, priority=50)
    session.commit()
    message = (
        "Yêu cầu đã được lưu; đang chờ quản trị mở lại kết nối DVCQG."
        if circuit_state == "open"
        else "Yêu cầu đã được xếp hàng để cập nhật dữ liệu."
    )
    return DashboardCollectionResponse(
        job_id=job.id,
        state=job.state,
        created=created,
        circuit_state=circuit_state,
        message=message,
    )


@router.get("/snapshots", response_model=list[SnapshotResponse], tags=["snapshots"])
def list_snapshots(
    session: DbSession,
    root_department_id: uuid.UUID | None = None,
    period_type: str | None = Query(default=None, pattern="^(month|quarter|year)$"),
    year: int | None = None,
    period_value: int | None = None,
    scope: str | None = Query(default=None, pattern="^(all|formality)$"),
    limit: int = Query(default=50, ge=1, le=200),
) -> list[Snapshot]:
    statement = select(Snapshot).order_by(Snapshot.created_at.desc()).limit(limit)
    if root_department_id is not None:
        statement = statement.where(Snapshot.root_department_id == root_department_id)
    if period_type is not None:
        statement = statement.where(Snapshot.period_type == period_type)
    if year is not None:
        statement = statement.where(Snapshot.year == year)
    if period_value is not None:
        statement = statement.where(Snapshot.period_value == period_value)
    if scope is not None:
        statement = statement.where(Snapshot.scope == scope)
    return list(session.scalars(statement))


@router.get("/formalities", response_model=list[FormalityResponse], tags=["formalities"])
def list_formalities(
    session: DbSession,
    code: str | None = None,
    department_id: uuid.UUID | None = None,
    limit: int = Query(default=50, ge=1, le=200),
) -> list[Formality]:
    statement = select(Formality).order_by(Formality.code).limit(limit)
    if code is not None:
        statement = statement.where(Formality.code == code)
    if department_id is not None:
        statement = statement.join(FormalityDepartment).where(
            FormalityDepartment.department_id == department_id,
            FormalityDepartment.relation_type == "applied",
        )
    return list(session.scalars(statement))


@router.get(
    "/formalities/{formality_id}",
    response_model=FormalityResponse,
    tags=["formalities"],
)
def get_formality(formality_id: uuid.UUID, session: DbSession) -> Formality:
    formality = session.get(Formality, formality_id)
    if formality is None:
        raise HTTPException(status_code=404, detail="Formality not found")
    return formality


@router.get("/snapshots/latest", response_model=SnapshotResponse, tags=["snapshots"])
def latest_snapshot(
    session: DbSession,
    root_department_id: uuid.UUID,
    period_type: str = Query(pattern="^(month|quarter|year)$"),
    year: int = Query(ge=2000, le=2200),
    scope: str = Query(default="all", pattern="^(all|formality)$"),
    period_value: int | None = None,
    formality_id: uuid.UUID | None = None,
) -> Snapshot:
    statement = (
        select(Snapshot)
        .where(
            Snapshot.root_department_id == root_department_id,
            Snapshot.period_type == period_type,
            Snapshot.year == year,
            Snapshot.scope == scope,
        )
        .order_by(Snapshot.created_at.desc())
    )
    if period_value is None:
        statement = statement.where(Snapshot.period_value.is_(None))
    else:
        statement = statement.where(Snapshot.period_value == period_value)
    if formality_id is None:
        statement = statement.where(Snapshot.formality_id.is_(None))
    else:
        statement = statement.where(Snapshot.formality_id == formality_id)
    snapshot = session.scalar(statement.limit(1))
    if snapshot is None:
        raise HTTPException(status_code=404, detail="Snapshot not found")
    return snapshot


@router.get("/snapshots/{snapshot_id}", response_model=SnapshotResponse, tags=["snapshots"])
def get_snapshot(snapshot_id: uuid.UUID, session: DbSession) -> Snapshot:
    snapshot = session.get(Snapshot, snapshot_id)
    if snapshot is None:
        raise HTTPException(status_code=404, detail="Snapshot not found")
    return snapshot


@router.get(
    "/snapshots/{snapshot_id}/datasets",
    response_model=list[DatasetResponse],
    tags=["snapshots"],
)
def list_datasets(snapshot_id: uuid.UUID, session: DbSession) -> list[Dataset]:
    if session.get(Snapshot, snapshot_id) is None:
        raise HTTPException(status_code=404, detail="Snapshot not found")
    return list(
        session.scalars(
            select(Dataset)
            .where(Dataset.snapshot_id == snapshot_id)
            .order_by(Dataset.position)
        )
    )


@router.get(
    "/datasets/{dataset_id}/entities",
    response_model=list[EntityResponse],
    tags=["datasets"],
)
def list_entities(
    dataset_id: uuid.UUID,
    session: DbSession,
    entity_kind: str | None = Query(default=None, pattern="^(root|child)$"),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=200),
) -> list[Entity]:
    if session.get(Dataset, dataset_id) is None:
        raise HTTPException(status_code=404, detail="Dataset not found")
    statement = (
        select(Entity)
        .options(selectinload(Entity.metrics))
        .where(Entity.dataset_id == dataset_id)
        .order_by(Entity.position)
        .offset(offset)
        .limit(limit)
    )
    if entity_kind is not None:
        statement = statement.where(Entity.entity_kind == entity_kind)
    return list(session.scalars(statement))
