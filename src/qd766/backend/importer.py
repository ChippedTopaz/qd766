from __future__ import annotations

import hashlib
import json
import uuid
from collections.abc import Iterable
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from .models import (
    Dataset,
    Department,
    Entity,
    Formality,
    FormalityDepartment,
    Metric,
    Snapshot,
)


class SnapshotImportError(ValueError):
    pass


class SnapshotConflict(SnapshotImportError):
    pass


def _ensure_department(
    session: Session,
    department_id: uuid.UUID,
    cache: dict[uuid.UUID, Department],
) -> Department:
    department = cache.get(department_id)
    if department is not None:
        return department
    department = session.get(Department, department_id)
    if department is None:
        department = Department(id=department_id, name=None)
        session.add(department)
    cache[department_id] = department
    return department


def _uuid(value: str, label: str) -> uuid.UUID:
    try:
        return uuid.UUID(value)
    except (TypeError, ValueError, AttributeError) as error:
        raise SnapshotImportError(f"Invalid UUID for {label}") from error


def _period_value(period: dict[str, Any]) -> int | None:
    period_type = period.get("type")
    if period_type == "month":
        return period.get("month")
    if period_type == "quarter":
        return period.get("quarter")
    if period_type == "year":
        return None
    raise SnapshotImportError("Unsupported period type")


def _snapshot_key(
    payload: dict[str, Any],
    root_department_id: uuid.UUID,
    raw_hashes: dict[str, str],
) -> str:
    period = payload["period"]
    value = _period_value(period)
    formality = payload.get("formalityId") or "all"
    logical_key = ":".join(
        [
            str(root_department_id),
            str(period["type"]),
            str(period["year"]),
            str(value or 0),
            str(payload["scope"]),
            str(formality),
        ]
    )
    content = json.dumps(raw_hashes, sort_keys=True, separators=(",", ":")).encode()
    content_hash = hashlib.sha256(content).hexdigest()
    return f"snapshot:v2:{logical_key}:{content_hash}"


def _raw_hashes(datasets: Iterable[dict[str, Any]]) -> dict[str, str]:
    return {
        item["group"]: _validate_raw_hash(item["raw"]["sha256"])
        for item in datasets
    }


def _validate_raw_hash(value: str) -> str:
    if len(value) != 64 or any(character not in "0123456789abcdef" for character in value.lower()):
        raise SnapshotImportError("Raw SHA-256 must contain 64 hexadecimal characters")
    return value.lower()


def _upsert_department(
    session: Session,
    entity: dict[str, Any],
    cache: dict[uuid.UUID, Department],
) -> Department:
    department_id = _uuid(entity["departmentId"], "departmentId")
    department = _ensure_department(session, department_id, cache)
    department.name = entity["departmentName"]
    department.code = entity.get("departmentCode")
    department.department_type = entity.get("departmentType")
    department.department_level = entity.get("departmentLevel")
    department.agency_level = entity.get("agencyLevel")
    department.attributes = entity.get("metadata", {})
    return department


def store_formality_page(session: Session, payload: dict[str, Any]) -> tuple[int, int]:
    """Upsert one `/reporting/formalities` page and its authoritative relations."""

    data = payload.get("data")
    items = data.get("items") if isinstance(data, dict) else None
    if not isinstance(items, list):
        raise SnapshotImportError("Formality response has no data.items list")
    department_cache: dict[uuid.UUID, Department] = {}
    relation_count = 0
    for item in items:
        formality_id = _uuid(item.get("id"), "formality id")
        owning_id = (
            _uuid(item["departmentId"], "formality departmentId")
            if item.get("departmentId")
            else None
        )
        relation_ids: list[tuple[uuid.UUID, str]] = []
        for field, relation_type in (
            ("appliedDepartmentIds", "applied"),
            ("publishingDepartmentIds", "publishing"),
        ):
            values = item.get(field, [])
            if not isinstance(values, list):
                raise SnapshotImportError(f"{field} must be a list")
            relation_ids.extend((_uuid(value, field), relation_type) for value in values)
        for department_id in {value for value, _ in relation_ids} | ({owning_id} if owning_id else set()):
            _ensure_department(session, department_id, department_cache)

        formality = session.get(Formality, formality_id)
        if formality is None:
            formality = Formality(id=formality_id, code=item["code"], name=item["name"])
            session.add(formality)
        formality.code = item["code"]
        formality.name = item["name"]
        formality.state = item.get("state")
        formality.owning_department_id = owning_id
        formality.attributes = {
            key: value
            for key, value in item.items()
            if key
            not in {
                "id",
                "code",
                "name",
                "state",
                "departmentId",
                "appliedDepartmentIds",
                "publishingDepartmentIds",
            }
        }
        session.execute(
            delete(FormalityDepartment).where(
                FormalityDepartment.formality_id == formality_id
            )
        )
        for department_id, relation_type in sorted(
            set(relation_ids), key=lambda value: (str(value[0]), value[1])
        ):
            session.add(
                FormalityDepartment(
                    formality_id=formality_id,
                    department_id=department_id,
                    relation_type=relation_type,
                )
            )
            relation_count += 1
    session.flush()
    return len(items), relation_count


def _add_entity(
    session: Session,
    dataset: Dataset,
    value: dict[str, Any],
    *,
    kind: str,
    position: int,
    department_cache: dict[uuid.UUID, Department],
) -> None:
    department = _upsert_department(session, value, department_cache)
    entity = Entity(
        dataset=dataset,
        department=department,
        entity_kind=kind,
        position=position,
        api_score=value.get("apiScore"),
        api_max_score=value.get("apiMaxScore"),
        api_ratio=value.get("apiRatio"),
        score_source=value.get("scoreSource", "dvcqg-api"),
        formula_applied=bool(value.get("formulaApplied", False)),
        parameters=value.get("parameters", {}),
        source_metadata=value.get("metadata", {}),
    )
    session.add(entity)
    for metric_position, item in enumerate(value.get("metrics", [])):
        entity.metrics.append(
            Metric(
                position=metric_position,
                code=item["code"],
                name=item["name"],
                numerator=item.get("numerator"),
                denominator=item.get("denominator"),
                ratio=item.get("ratio"),
                api_score=item.get("apiScore"),
                api_max_score=item.get("apiMaxScore"),
                extras=item.get("extras", {}),
            )
        )


def store_normalized_snapshot(session: Session, payload: dict[str, Any], *, observation_id: str | None = None) -> Snapshot:
    """Persist one complete normalized snapshot in a single transaction.

    Re-importing the exact same snapshot is idempotent. Reusing the same logical
    key with different raw hashes is rejected so verified history stays immutable.
    """

    status = payload.get("status", {})
    if status.get("state") != "complete" or status.get("missingGroups"):
        raise SnapshotImportError("Only complete snapshots can be persisted")
    datasets = payload.get("datasets")
    if not isinstance(datasets, list) or not datasets:
        raise SnapshotImportError("Snapshot has no datasets")
    loaded_groups = status.get("loadedGroups", [])
    if set(loaded_groups) != {item.get("group") for item in datasets}:
        raise SnapshotImportError("Loaded groups do not match datasets")

    root_ids = {_uuid(item["root"]["departmentId"], "root department") for item in datasets}
    if len(root_ids) != 1:
        raise SnapshotImportError("Datasets do not share one root department")
    root_department_id = next(iter(root_ids))
    raw_hashes = _raw_hashes(datasets)
    key = _snapshot_key(payload, root_department_id, raw_hashes)
    if observation_id is not None:
        # A new actual collection can be a new immutable observation even if its
        # content is unchanged. Same observation remains idempotent on resume.
        key += ':observed:' + hashlib.sha256(observation_id.encode()).hexdigest()[:24]
    existing = session.scalar(select(Snapshot).where(Snapshot.snapshot_key == key))
    if existing is not None:
        existing_hashes = {item.group_name: item.raw_sha256 for item in existing.datasets}
        if existing_hashes == raw_hashes:
            return existing
        raise SnapshotConflict("Content-addressed snapshot key collision")

    department_cache: dict[uuid.UUID, Department] = {}
    root_department = _upsert_department(session, datasets[0]["root"], department_cache)
    period = payload["period"]
    snapshot = Snapshot(
        snapshot_key=key,
        schema_version=int(payload.get("schemaVersion", 1)),
        root_department=root_department,
        period_type=period["type"],
        year=int(period["year"]),
        period_value=_period_value(period),
        scope=payload["scope"],
        formality_id=(
            _uuid(payload["formalityId"], "formalityId")
            if payload.get("formalityId")
            else None
        ),
        state=status["state"],
        province_aggregated_score=payload.get("provinceAggregatedScore"),
        province_aggregated_maximum=payload.get("provinceAggregatedMaximum"),
        policy=payload.get("scorePolicy", {}),
        status_detail=status,
        created_at=datetime.now(timezone.utc),
    )
    session.add(snapshot)
    for position, item in enumerate(datasets):
        dataset = Dataset(
            snapshot=snapshot,
            position=position,
            group_name=item["group"],
            schema_kind=item["schemaKind"],
            formula_status=item["formulaStatus"],
            score_policy=item["scorePolicy"],
            raw_path=item["raw"]["path"],
            raw_sha256=raw_hashes[item["group"]],
            details=item.get("details", {}),
        )
        session.add(dataset)
        _add_entity(
            session,
            dataset,
            item["root"],
            kind="root",
            position=0,
            department_cache=department_cache,
        )
        for child_position, child in enumerate(item.get("children", []), start=1):
            _add_entity(
                session,
                dataset,
                child,
                kind="child",
                position=child_position,
                department_cache=department_cache,
            )
    session.flush()
    return snapshot
