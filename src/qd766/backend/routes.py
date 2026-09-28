from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, selectinload

from .dashboard import dashboard_payload
from .database import get_session
from .models import CollectionJob, Dataset, Entity, Formality, FormalityDepartment, Snapshot
from .schemas import (
    CollectionJobResponse,
    DatasetResponse,
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


@router.get("/dashboard", tags=["dashboard"])
def dashboard(
    session: DbSession,
    root_department_id: uuid.UUID | None = None,
) -> dict:
    if root_department_id is None:
        root_department_id = session.scalar(
            select(Snapshot.root_department_id)
            .where(Snapshot.state == "complete")
            .order_by(Snapshot.created_at.desc())
            .limit(1)
        )
    if root_department_id is None:
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
        .where(Snapshot.state == "complete")
        .order_by(Snapshot.year.desc(), Snapshot.period_type, Snapshot.period_value.desc())
    )
    statement = statement.where(Snapshot.root_department_id == root_department_id)
    snapshots = list(session.scalars(statement).unique())
    if not snapshots:
        raise HTTPException(status_code=404, detail="No complete snapshots found")
    formality_id = next(
        (snapshot.formality_id for snapshot in snapshots if snapshot.formality_id is not None),
        None,
    )
    formality = session.get(Formality, formality_id) if formality_id else None
    return dashboard_payload(snapshots, formality)


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
