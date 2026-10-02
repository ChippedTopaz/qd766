from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy import func, select, text
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session, selectinload

from qd766.province_catalog import (
    PROVINCES,
    ProvinceCatalogError,
    ProvinceCatalogFormatError,
    ProvinceCatalogUnavailable,
)
from qd766.periods import PeriodSelection
from qd766.province_roots import load_province_roots, province_root

from .batches import enqueue_next_batch_item, resume_batch
from .dashboard import (
    NATIONAL_GROUP_CODES,
    NATIONAL_GROUP_MAXIMUMS,
    dashboard_payload,
    snapshot_payload,
)
from .database import get_session
from .jobs import enqueue_job, request_idempotency_key
from .national_summaries import latest_national_summary
from .models import (
    CollectionBatch,
    CollectionBatchItem,
    CollectionControl,
    CollectionJob,
    Dataset,
    Department,
    Entity,
    Formality,
    FormalityDepartment,
    Metric,
    NationalSummarySnapshot,
    ProvinceCollectionBatch,
    ProvinceCollectionBatchItem,
    Snapshot,
)
from .schemas import (
    CollectionControlResponse,
    CollectionJobResponse,
    DatasetResponse,
    DashboardCollectionRequest,
    DashboardCollectionResponse,
    EntityResponse,
    FormalityBatchRequest,
    FormalityBatchResponse,
    FormalityResponse,
    HealthResponse,
    NationalSummaryResponse,
    ProvinceCollectionBatchItemResponse,
    ProvinceCollectionBatchResponse,
    SnapshotResponse,
)

router = APIRouter(prefix="/api/v1")
DbSession = Annotated[Session, Depends(get_session)]


def _merge_national_rankings(
    detailed: list[dict], summary: NationalSummarySnapshot
) -> list[dict]:
    by_root = {item["rootDepartmentId"]: item for item in detailed}
    code_to_group = {code: group for group, code in NATIONAL_GROUP_CODES.items()}
    for row in summary.response_data.get("evaluation", []):
        root_id = str(row["departmentId"])
        item = by_root.setdefault(
            root_id,
            {
                "rootDepartmentId": root_id,
                "provinceName": row["departmentName"],
                "groups": {},
            },
        )
        item["provinceName"] = row["departmentName"]
        item["totalScore"] = float(row["totalScore"])
        item["totalMaximum"] = 100.0
        item["capturedAt"] = summary.captured_at.isoformat()
        for code, score in row.get("groupScores", {}).items():
            group = code_to_group.get(code)
            if group is None:
                continue
            group_item = item["groups"].setdefault(
                group,
                {"parameters": {}, "metrics": {}},
            )
            group_item["score"] = float(score)
            group_item["maximum"] = NATIONAL_GROUP_MAXIMUMS[group]
    return sorted(by_root.values(), key=lambda item: item["provinceName"])


def _collection_job_responses(
    session: Session, jobs: list[CollectionJob]
) -> list[CollectionJobResponse]:
    department_ids = {
        uuid.UUID(str(value))
        for job in jobs
        if (value := job.request.get("rootDepartmentId")) is not None
    }
    formality_ids = {
        uuid.UUID(str(value))
        for job in jobs
        if (value := job.request.get("formalityId")) is not None
    }
    departments = (
        {
            item.id: item
            for item in session.scalars(
                select(Department).where(Department.id.in_(department_ids))
            )
        }
        if department_ids
        else {}
    )
    formalities = (
        {
            item.id: item
            for item in session.scalars(
                select(Formality).where(Formality.id.in_(formality_ids))
            )
        }
        if formality_ids
        else {}
    )
    responses: list[CollectionJobResponse] = []
    for job in jobs:
        department_value = job.request.get("rootDepartmentId")
        formality_value = job.request.get("formalityId")
        department = (
            departments.get(uuid.UUID(str(department_value)))
            if department_value is not None
            else None
        )
        formality = (
            formalities.get(uuid.UUID(str(formality_value)))
            if formality_value is not None
            else None
        )
        province_name = None
        if department is not None:
            province_name = department.attributes.get("provinceName") or department.name
        responses.append(
            CollectionJobResponse.model_validate(job).model_copy(
                update={
                    "province_name": province_name,
                    "formality_code": formality.code if formality else None,
                    "formality_name": formality.name if formality else None,
                }
            )
        )
    return responses


def _province_code_for_name(department_name: str | None) -> str | None:
    normalized = (department_name or "").casefold()
    return next(
        (code for code, (name, _) in PROVINCES.items() if name.casefold() in normalized),
        None,
    )


def _root_department_for_province(
    session: Session, province_code: str | None
) -> uuid.UUID | None:
    if province_code is None:
        return session.scalar(
            select(Snapshot.root_department_id)
            .where(Snapshot.state == "complete")
            .order_by(Snapshot.created_at.desc())
            .limit(1)
        )
    province = PROVINCES.get(province_code)
    if province is None:
        return None
    registered = province_root(province_code)
    if registered is not None:
        return registered.root_department_id
    province_name = province[0].casefold()
    candidates = session.execute(
        select(Snapshot.root_department_id, Department.name)
        .join(Department, Department.id == Snapshot.root_department_id)
        .where(Snapshot.state == "complete")
        .order_by(Snapshot.created_at.desc())
    )
    return next(
        (
            root_id
            for root_id, department_name in candidates
            if province_name in (department_name or "").casefold()
        ),
        None,
    )


@router.get("/province-catalog", tags=["formalities"])
def list_province_catalogs() -> list[dict[str, str]]:
    return [
        {"code": code, "name": name, "slug": slug}
        for code, (name, slug) in PROVINCES.items()
    ]


@router.get("/province-catalog/{province_code}", tags=["formalities"])
def get_province_catalog(
    province_code: str,
    request: Request,
    response: Response,
    level: str | None = Query(default=None, pattern="^(province|ward)$"),
    field: str | None = None,
    q: str | None = None,
    include_internal: bool = True,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
) -> dict:
    normalized_code = province_code.strip().zfill(2)
    if normalized_code not in PROVINCES:
        raise HTTPException(status_code=404, detail="Province catalog not found")
    cache_key = f"{normalized_code}:internal={str(include_internal).lower()}"

    def load_catalog():
        return request.app.state.province_catalog_client.load(
            normalized_code,
            include_internal=include_internal,
        )

    try:
        catalog, cache_result = request.app.state.province_catalog_cache.get_or_load(
            cache_key,
            load_catalog,
        )
        selected = catalog.select(level=level, field=field, query=q)
    except ProvinceCatalogUnavailable as error:
        raise HTTPException(status_code=503, detail="Province catalog source unavailable") from error
    except ProvinceCatalogFormatError as error:
        raise HTTPException(status_code=502, detail="Province catalog source is invalid") from error
    except ProvinceCatalogError as error:
        raise HTTPException(status_code=502, detail="Province catalog could not be loaded") from error

    response.headers["X-QD766-Catalog-Cache"] = cache_result
    response.headers["Cache-Control"] = "private, max-age=300"
    items = selected[offset : offset + limit]
    return {
        "source": "am-sieu-toc-data:data/index.json + niemyet/isVertical.json",
        "schemaVersion": 1,
        "province": {
            "code": catalog.province.code,
            "name": catalog.province.name,
            "slug": catalog.province.slug,
        },
        "masterUpdatedAt": catalog.master_updated_at,
        "rulesSha256": catalog.rules_sha256,
        "selection": {
            "level": level,
            "field": field,
            "query": q,
            "includeInternal": include_internal,
            "formalityCount": len(selected),
            "totalCount": catalog.total_count,
            "provinceCount": catalog.province_count,
            "wardCount": catalog.ward_count,
        },
        "offset": offset,
        "limit": limit,
        "fields": list(catalog.fields),
        "items": [
            {
                "id": item.id,
                "code": item.code,
                "name": item.name,
                "field": item.field,
                "publishingAgency": item.publishing_agency,
                "executionLevels": list(item.execution_levels),
                "formalityType": item.formality_type,
                "state": item.state,
                "isVertical": item.is_vertical,
            }
            for item in items
        ],
    }


@router.get("/province-catalog/{province_code}/preview", tags=["formalities"])
def preview_province_catalog(
    province_code: str,
    request: Request,
    response: Response,
    session: DbSession,
    period_type: str = Query(pattern="^(month|quarter|year)$"),
    year: int = Query(ge=2000, le=2200),
    period_value: int | None = None,
    level: str | None = Query(default=None, pattern="^(province|ward)$"),
    field: str | None = None,
    q: str | None = None,
    include_internal: bool = True,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
) -> dict:
    normalized_code = province_code.strip().zfill(2)
    if normalized_code not in PROVINCES:
        raise HTTPException(status_code=404, detail="Province catalog not found")
    cache_key = f"{normalized_code}:internal={str(include_internal).lower()}"
    try:
        catalog, cache_result = request.app.state.province_catalog_cache.get_or_load(
            cache_key,
            lambda: request.app.state.province_catalog_client.load(
                normalized_code, include_internal=include_internal
            ),
        )
        selected = catalog.select(level=level, field=field, query=q)
    except ProvinceCatalogUnavailable as error:
        raise HTTPException(status_code=503, detail="Province catalog source unavailable") from error
    except ProvinceCatalogError as error:
        raise HTTPException(status_code=502, detail="Province catalog source is invalid") from error

    root_department_id = _root_department_for_province(session, normalized_code)
    available_statement = select(Snapshot.formality_id).where(
        Snapshot.state == "complete",
        Snapshot.scope == "formality",
        Snapshot.period_type == period_type,
        Snapshot.year == year,
    )
    if root_department_id is not None:
        available_statement = available_statement.where(
            Snapshot.root_department_id == root_department_id
        )
    available_statement = (
        available_statement.where(Snapshot.period_value.is_(None))
        if period_value is None
        else available_statement.where(Snapshot.period_value == period_value)
    )
    available_ids = {
        str(item) for item in session.scalars(available_statement) if item is not None
    }
    available_count = sum(item.id in available_ids for item in selected)
    page = selected[offset : offset + limit]
    response.headers["X-QD766-Catalog-Cache"] = cache_result
    response.headers["Cache-Control"] = "private, max-age=60"
    return {
        "province": {
            "code": catalog.province.code,
            "name": catalog.province.name,
        },
        "filters": {
            "level": level,
            "field": field,
            "query": q,
            "includeInternal": include_internal,
        },
        "period": {
            "type": period_type,
            "year": year,
            "value": period_value,
        },
        "counts": {
            "selected": len(selected),
            "available": available_count,
            "missing": len(selected) - available_count,
        },
        "fields": list(catalog.fields),
        "offset": offset,
        "limit": limit,
        "items": [
            {
                "id": item.id,
                "code": item.code,
                "name": item.name,
                "field": item.field,
                "publishingAgency": item.publishing_agency,
                "executionLevels": list(item.execution_levels),
                "available": item.id in available_ids,
            }
            for item in page
        ],
    }


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


@router.post(
    "/formality-batches",
    response_model=FormalityBatchResponse,
    status_code=status.HTTP_202_ACCEPTED,
    tags=["collection-batches"],
)
def create_formality_batch(
    payload: FormalityBatchRequest,
    request: Request,
    session: DbSession,
) -> CollectionBatch:
    if payload.province_code not in PROVINCES:
        raise HTTPException(status_code=404, detail="Province catalog not found")
    root_department_id = _root_department_for_province(session, payload.province_code)
    if root_department_id is None:
        raise HTTPException(status_code=409, detail="No root department is available for province")

    cache_key = f"{payload.province_code}:internal={str(payload.include_internal).lower()}"
    try:
        catalog, _ = request.app.state.province_catalog_cache.get_or_load(
            cache_key,
            lambda: request.app.state.province_catalog_client.load(
                payload.province_code,
                include_internal=payload.include_internal,
            ),
        )
    except ProvinceCatalogUnavailable as error:
        raise HTTPException(status_code=503, detail="Province catalog source unavailable") from error
    except ProvinceCatalogError as error:
        raise HTTPException(status_code=502, detail="Province catalog source is invalid") from error
    selected = catalog.select(
        level=payload.level,
        field=payload.field,
        query=payload.query,
    )
    if not selected:
        raise HTTPException(status_code=422, detail="No formalities match the selected filters")

    key_request = {
        "kind": "formality-batch",
        "provinceCode": payload.province_code,
        "rootDepartmentId": str(root_department_id),
        "periodType": payload.period_type,
        "year": payload.year,
        "periodValue": payload.period_value,
        "level": payload.level,
        "field": payload.field,
        "query": (payload.query or "").strip(),
        "includeInternal": payload.include_internal,
        "catalogUpdatedAt": catalog.master_updated_at,
        "rulesSha256": catalog.rules_sha256,
    }
    idempotency_key = request_idempotency_key(key_request).replace(
        "collection:v1:", "batch:v1:"
    )
    existing = session.scalar(
        select(CollectionBatch).where(
            CollectionBatch.idempotency_key == idempotency_key
        )
    )
    if existing is not None:
        return existing

    available_statement = select(Snapshot.formality_id).where(
        Snapshot.state == "complete",
        Snapshot.scope == "formality",
        Snapshot.root_department_id == root_department_id,
        Snapshot.period_type == payload.period_type,
        Snapshot.year == payload.year,
    )
    available_statement = (
        available_statement.where(Snapshot.period_value.is_(None))
        if payload.period_value is None
        else available_statement.where(Snapshot.period_value == payload.period_value)
    )
    available_ids = {
        str(value) for value in session.scalars(available_statement) if value is not None
    }
    selected_ids = {uuid.UUID(item.id) for item in selected}
    known_ids = set(
        session.scalars(select(Formality.id).where(Formality.id.in_(selected_ids)))
    )
    batch = CollectionBatch(
        idempotency_key=idempotency_key,
        state="queued",
        province_code=payload.province_code,
        root_department_id=root_department_id,
        period_type=payload.period_type,
        year=payload.year,
        period_value=payload.period_value,
        filters={
            "level": payload.level,
            "field": payload.field,
            "query": payload.query,
            "includeInternal": payload.include_internal,
        },
        catalog_version=f"{catalog.master_updated_at}:{catalog.rules_sha256}",
        total_items=len(selected),
        available_items=sum(item.id in available_ids for item in selected),
        completed_items=0,
        failed_items=0,
    )
    try:
        with session.begin_nested():
            session.add(batch)
            session.flush()
    except IntegrityError:
        existing = session.scalar(
            select(CollectionBatch).where(
                CollectionBatch.idempotency_key == idempotency_key
            )
        )
        if existing is None:
            raise
        return existing
    new_formalities = [
        {
            "id": uuid.UUID(item.id),
            "code": item.code,
            "name": item.name,
            "state": item.state or None,
            "attributes": {
                "field": item.field,
                "publishingAgency": item.publishing_agency,
                "executionLevels": list(item.execution_levels),
                "catalogProvinceCode": payload.province_code,
            },
        }
        for item in selected
        if uuid.UUID(item.id) not in known_ids
    ]
    if new_formalities:
        dialect_name = session.get_bind().dialect.name
        if dialect_name == "postgresql":
            session.execute(
                postgresql_insert(Formality)
                .values(new_formalities)
                .on_conflict_do_nothing()
            )
        elif dialect_name == "sqlite":
            session.execute(
                sqlite_insert(Formality)
                .values(new_formalities)
                .on_conflict_do_nothing()
            )
        else:
            for values in new_formalities:
                session.add(Formality(**values))
        session.flush()

    for position, item in enumerate(selected):
        formality_id = uuid.UUID(item.id)
        session.add(
            CollectionBatchItem(
                batch_id=batch.id,
                position=position,
                formality_id=formality_id,
                formality_code=item.code,
                formality_name=item.name,
                state="skipped" if item.id in available_ids else "pending",
            )
        )
    session.flush()
    enqueue_next_batch_item(session, batch)
    session.commit()
    return batch


@router.get(
    "/formality-batches",
    response_model=list[FormalityBatchResponse],
    tags=["collection-batches"],
)
def list_formality_batches(
    session: DbSession,
    limit: int = Query(default=20, ge=1, le=100),
) -> list[CollectionBatch]:
    return list(
        session.scalars(
            select(CollectionBatch)
            .order_by(CollectionBatch.created_at.desc())
            .limit(limit)
        )
    )


@router.get(
    "/formality-batches/{batch_id}",
    response_model=FormalityBatchResponse,
    tags=["collection-batches"],
)
def get_formality_batch(batch_id: uuid.UUID, session: DbSession) -> CollectionBatch:
    batch = session.get(CollectionBatch, batch_id)
    if batch is None:
        raise HTTPException(status_code=404, detail="Collection batch not found")
    return batch


@router.post(
    "/formality-batches/{batch_id}/resume",
    response_model=FormalityBatchResponse,
    tags=["collection-batches"],
)
def resume_formality_batch(batch_id: uuid.UUID, session: DbSession) -> CollectionBatch:
    batch = session.get(CollectionBatch, batch_id)
    if batch is None:
        raise HTTPException(status_code=404, detail="Collection batch not found")
    if batch.state not in {"failed", "halted"}:
        raise HTTPException(status_code=409, detail="Collection batch is not resumable")
    control = session.get(CollectionControl, "dvcqg")
    if control is not None and control.circuit_state == "open":
        raise HTTPException(status_code=409, detail="DVCQG circuit is open")
    resume_batch(session, batch)
    session.commit()
    return batch


@router.get(
    "/province-batches",
    response_model=list[ProvinceCollectionBatchResponse],
    tags=["collection-batches"],
)
def list_province_batches(
    session: DbSession,
    limit: int = Query(default=20, ge=1, le=100),
) -> list[ProvinceCollectionBatch]:
    """Expose read-only progress; national batch creation remains operator-only."""
    return list(
        session.scalars(
            select(ProvinceCollectionBatch)
            .order_by(ProvinceCollectionBatch.created_at.desc())
            .limit(limit)
        )
    )


@router.get(
    "/province-batches/{batch_id}",
    response_model=ProvinceCollectionBatchResponse,
    tags=["collection-batches"],
)
def get_province_batch(
    batch_id: uuid.UUID,
    session: DbSession,
) -> ProvinceCollectionBatch:
    batch = session.get(ProvinceCollectionBatch, batch_id)
    if batch is None:
        raise HTTPException(status_code=404, detail="Province collection batch not found")
    return batch


@router.get(
    "/province-batches/{batch_id}/items",
    response_model=list[ProvinceCollectionBatchItemResponse],
    tags=["collection-batches"],
)
def list_province_batch_items(
    batch_id: uuid.UUID,
    session: DbSession,
) -> list[ProvinceCollectionBatchItem]:
    if session.get(ProvinceCollectionBatch, batch_id) is None:
        raise HTTPException(status_code=404, detail="Province collection batch not found")
    return list(
        session.scalars(
            select(ProvinceCollectionBatchItem)
            .where(ProvinceCollectionBatchItem.batch_id == batch_id)
            .order_by(ProvinceCollectionBatchItem.position)
        )
    )


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
) -> list[CollectionJobResponse]:
    statement = select(CollectionJob).order_by(CollectionJob.created_at.desc()).limit(limit)
    if state is not None:
        statement = statement.where(CollectionJob.state == state)
    return _collection_job_responses(session, list(session.scalars(statement)))


@router.get(
    "/collection-jobs/{job_id}",
    response_model=CollectionJobResponse,
    tags=["collection-jobs"],
)
def get_collection_job(job_id: uuid.UUID, session: DbSession) -> CollectionJobResponse:
    job = session.get(CollectionJob, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Collection job not found")
    return _collection_job_responses(session, [job])[0]


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


@router.get("/dashboard/provinces", tags=["dashboard"])
def dashboard_provinces(session: DbSession) -> list[dict]:
    rows = list(
        session.execute(
            select(
                Snapshot.root_department_id,
                Department.name,
                Department.code,
                func.count(Snapshot.id),
                func.max(Snapshot.created_at),
            )
            .join(Department, Department.id == Snapshot.root_department_id)
            .where(Snapshot.state == "complete")
            .group_by(Snapshot.root_department_id, Department.name, Department.code)
            .order_by(Department.name)
        )
    )
    observed = {
        root_id: {
            "name": name,
            "departmentCode": department_code,
            "snapshotCount": snapshot_count,
            "latestSnapshotAt": latest_snapshot_at,
        }
        for root_id, name, department_code, snapshot_count, latest_snapshot_at in rows
    }
    roots = load_province_roots()
    if roots:
        return [
            {
                "id": str(root.root_department_id),
                "name": observed.get(root.root_department_id, {}).get(
                    "name", root.department_name
                ),
                "departmentCode": observed.get(root.root_department_id, {}).get(
                    "departmentCode", root.department_code
                ),
                "provinceCode": root.province_code,
                "snapshotCount": observed.get(root.root_department_id, {}).get(
                    "snapshotCount", 0
                ),
                "latestSnapshotAt": observed.get(root.root_department_id, {}).get(
                    "latestSnapshotAt"
                ),
                "available": root.root_department_id in observed,
            }
            for root in sorted(roots.values(), key=lambda item: item.province_name)
        ]
    return [
        {
            "id": str(root_id),
            "name": name,
            "departmentCode": department_code,
            "provinceCode": _province_code_for_name(name),
            "snapshotCount": snapshot_count,
            "latestSnapshotAt": latest_snapshot_at,
            "available": True,
        }
        for root_id, name, department_code, snapshot_count, latest_snapshot_at in rows
    ]


@router.get(
    "/national-summaries",
    response_model=list[NationalSummaryResponse],
    tags=["national-summaries"],
)
def list_national_summaries(
    session: DbSession,
    limit: int = Query(default=50, ge=1, le=200),
) -> list[NationalSummarySnapshot]:
    return list(
        session.scalars(
            select(NationalSummarySnapshot)
            .order_by(NationalSummarySnapshot.captured_at.desc())
            .limit(limit)
        )
    )


@router.get("/national-summaries/latest", tags=["national-summaries"])
def get_latest_national_summary(
    session: DbSession,
    period_type: str = Query(pattern="^(month|quarter|year)$"),
    year: int = Query(ge=2000, le=2200),
    period_value: int | None = None,
) -> dict:
    summary = latest_national_summary(
        session, PeriodSelection(period_type, year, period_value)
    )
    if summary is None:
        raise HTTPException(status_code=404, detail="National summary not found")
    return {
        "id": str(summary.id),
        "periodType": summary.period_type,
        "year": summary.year,
        "periodValue": summary.period_value,
        "provinceCount": summary.province_count,
        "completenessState": summary.completeness_state,
        "groupCount": summary.group_count,
        "groupCodes": summary.group_codes,
        "rawSha256": summary.raw_sha256,
        "capturedAt": summary.captured_at.isoformat(),
        "data": summary.response_data,
    }


@router.get("/dashboard/province-rankings", tags=["dashboard"])
def dashboard_province_rankings(
    session: DbSession,
    period_type: str = Query(pattern="^(month|quarter|year)$"),
    year: int = Query(ge=2000, le=2200),
    scope: str = Query(default="all", pattern="^(all|formality)$"),
    period_value: int | None = None,
    formality_id: uuid.UUID | None = None,
) -> list[dict]:
    """Return only provincial root scores needed for cross-province ranking."""
    statement = (
        select(
            Snapshot.id,
            Snapshot.root_department_id,
            Department.name,
            Snapshot.created_at,
            Dataset.group_name,
            Entity.id,
            Entity.api_score,
            Entity.api_max_score,
            Entity.parameters,
        )
        .join(Department, Department.id == Snapshot.root_department_id)
        .join(Dataset, Dataset.snapshot_id == Snapshot.id)
        .join(Entity, Entity.dataset_id == Dataset.id)
        .where(
            Snapshot.state == "complete",
            Snapshot.period_type == period_type,
            Snapshot.year == year,
            Snapshot.scope == scope,
            Entity.entity_kind == "root",
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
    latest_by_root: dict[uuid.UUID, dict] = {}
    rows = session.execute(statement)
    entity_groups: dict[int, dict] = {}
    for snapshot_id, root_id, name, created_at, group_name, entity_id, score, maximum, parameters in rows:
        item = latest_by_root.setdefault(
            root_id,
            {
                "snapshotId": snapshot_id,
                "rootDepartmentId": str(root_id),
                "provinceName": name,
                "groups": {},
                "capturedAt": created_at.isoformat(),
            },
        )
        if item["snapshotId"] != snapshot_id:
            continue
        item["groups"][group_name] = {
            "score": float(score) if score is not None else None,
            "maximum": float(maximum) if maximum is not None else None,
            "parameters": parameters,
            "metrics": {},
        }
        entity_groups[entity_id] = item["groups"][group_name]
    if entity_groups:
        metric_rows = session.execute(
            select(
                Metric.entity_id,
                Metric.code,
                Metric.name,
                Metric.ratio,
                Metric.api_score,
                Metric.api_max_score,
            ).where(Metric.entity_id.in_(entity_groups))
        )
        for entity_id, code, name, ratio, score, maximum in metric_rows:
            entity_groups[entity_id]["metrics"][code] = {
                "name": name,
                "ratio": float(ratio) if ratio is not None else None,
                "score": float(score) if score is not None else None,
                "maximum": float(maximum) if maximum is not None else None,
            }
    result: list[dict] = []
    for item in latest_by_root.values():
        groups = item["groups"]
        scores = [item["score"] for item in groups.values()]
        maximums = [item["maximum"] for item in groups.values()]
        complete = groups and all(value is not None for value in scores + maximums)
        result.append(
            {
                "rootDepartmentId": item["rootDepartmentId"],
                "provinceName": item["provinceName"],
                "totalScore": round(sum(scores), 2) if complete else None,
                "totalMaximum": round(sum(maximums), 2) if complete else None,
                "groups": groups,
                "capturedAt": item["capturedAt"],
            }
        )
    ordered = sorted(result, key=lambda item: item["provinceName"])
    if scope == "all" and formality_id is None:
        summary = latest_national_summary(
            session, PeriodSelection(period_type, year, period_value)
        )
        if summary is not None:
            return _merge_national_rankings(ordered, summary)
    return ordered


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
        summaries: dict[tuple[str, int, int | None], NationalSummarySnapshot] = {}
        for key in {
            (item.period_type, item.year, item.period_value) for item in snapshots
        }:
            summary = latest_national_summary(session, PeriodSelection(*key))
            if summary is not None:
                summaries[key] = summary
        return dashboard_payload(snapshots, formality, summaries)

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
        national_summary = latest_national_summary(
            session,
            PeriodSelection(period_type, year, period_value),
        )
        item = snapshot_payload(selected, national_summary)
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
    request: Request,
    session: DbSession,
) -> DashboardCollectionResponse:
    if payload.scope == "all":
        raise HTTPException(
            status_code=403,
            detail=(
                "Dữ liệu tổng hợp toàn tỉnh do hệ thống tự động cập nhật; "
                "người dùng không thể tạo yêu cầu thu thập phạm vi tất cả TTHC."
            ),
        )
    root_department_id = _root_department_for_province(session, payload.province_code)
    if root_department_id is None:
        raise HTTPException(status_code=409, detail="No root department is available for province")
    if payload.formality_id is not None and session.get(Formality, payload.formality_id) is None:
        if payload.province_code is None or payload.formality_code is None:
            raise HTTPException(status_code=404, detail="Formality not found")
        cache_key = f"{payload.province_code}:internal=true"
        try:
            catalog, _ = request.app.state.province_catalog_cache.get_or_load(
                cache_key,
                lambda: request.app.state.province_catalog_client.load(
                    payload.province_code, include_internal=True
                ),
            )
        except ProvinceCatalogUnavailable as error:
            raise HTTPException(
                status_code=503, detail="Province catalog source unavailable"
            ) from error
        except ProvinceCatalogError as error:
            raise HTTPException(
                status_code=502, detail="Province catalog source is invalid"
            ) from error
        catalog_item = next(
            (
                item
                for item in catalog.formalities
                if item.id == str(payload.formality_id)
                and item.code == payload.formality_code
            ),
            None,
        )
        if catalog_item is None:
            raise HTTPException(status_code=404, detail="Formality not found in province catalog")
        values = {
            "id": payload.formality_id,
            "code": catalog_item.code,
            "name": catalog_item.name,
            "state": catalog_item.state or None,
            "attributes": {
                "field": catalog_item.field,
                "publishingAgency": catalog_item.publishing_agency,
                "executionLevels": list(catalog_item.execution_levels),
                "catalogProvinceCode": payload.province_code,
            },
        }
        dialect_name = session.get_bind().dialect.name
        if dialect_name == "postgresql":
            session.execute(
                postgresql_insert(Formality).values(values).on_conflict_do_nothing()
            )
        elif dialect_name == "sqlite":
            session.execute(
                sqlite_insert(Formality).values(values).on_conflict_do_nothing()
            )
        else:
            session.add(Formality(**values))
        session.flush()
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
        else (
            "Yêu cầu của bạn đã được đưa vào hàng đợi. "
            "Hệ thống sẽ thông báo khi dữ liệu được thống kê xong."
        )
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
