from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


def to_camel(value: str) -> str:
    head, *tail = value.split("_")
    return head + "".join(part.capitalize() for part in tail)


class ApiModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        from_attributes=True,
    )


class HealthResponse(ApiModel):
    status: str


class SnapshotResponse(ApiModel):
    id: uuid.UUID
    root_department_id: uuid.UUID
    period_type: str
    year: int
    period_value: int | None
    scope: str
    formality_id: uuid.UUID | None
    state: str
    province_aggregated_score: Decimal | None
    province_aggregated_maximum: Decimal | None
    created_at: datetime


class DatasetResponse(ApiModel):
    id: uuid.UUID
    snapshot_id: uuid.UUID
    position: int
    group_name: str = Field(serialization_alias="group")
    schema_kind: str
    formula_status: str
    score_policy: str
    raw_path: str
    raw_sha256: str
    details: dict[str, Any]


class MetricResponse(ApiModel):
    code: str
    name: str
    numerator: Decimal | None
    denominator: Decimal | None
    ratio: Decimal | None
    api_score: Decimal | None
    api_max_score: Decimal | None
    extras: dict[str, Any]


class EntityResponse(ApiModel):
    id: int
    department_id: uuid.UUID
    entity_kind: str
    position: int
    api_score: Decimal | None
    api_max_score: Decimal | None
    api_ratio: Decimal | None
    score_source: str
    formula_applied: bool
    parameters: dict[str, Any]
    source_metadata: dict[str, Any]
    metrics: list[MetricResponse]


class FormalityResponse(ApiModel):
    id: uuid.UUID
    code: str
    name: str
    state: str | None
    owning_department_id: uuid.UUID | None
    attributes: dict[str, Any]


class CollectionJobResponse(ApiModel):
    id: uuid.UUID
    idempotency_key: str
    state: str
    priority: int
    request: dict[str, Any]
    attempts: int
    next_run_at: datetime | None
    locked_at: datetime | None
    locked_by: str | None
    error: dict[str, Any] | None
    created_at: datetime
    updated_at: datetime
