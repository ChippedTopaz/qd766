from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from qd766.periods import PeriodSelection


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
    province_name: str | None = None
    formality_code: str | None = None
    formality_name: str | None = None
    created_at: datetime
    updated_at: datetime


class CollectionControlResponse(ApiModel):
    key: str
    circuit_state: str
    reason: str | None
    detail: dict[str, Any] | None
    opened_at: datetime | None
    lease_locked_at: datetime | None
    lease_locked_by: str | None
    updated_at: datetime


class DashboardCollectionRequest(ApiModel):
    period_type: Literal["month", "quarter", "year"]
    year: int = Field(ge=2026, le=2200)
    period_value: int | None = None
    scope: Literal["all", "formality"] = "all"
    formality_id: uuid.UUID | None = None
    province_code: str | None = Field(default=None, pattern=r"^\d{2}$")
    formality_code: str | None = None

    @model_validator(mode="after")
    def validate_selection(self) -> "DashboardCollectionRequest":
        PeriodSelection(self.period_type, self.year, self.period_value).validate_collectable()
        if self.scope == "all" and self.formality_id is not None:
            raise ValueError("all scope must not include formalityId")
        if self.scope == "formality" and self.formality_id is None:
            raise ValueError("formality scope requires formalityId")
        return self


class DashboardCollectionResponse(ApiModel):
    job_id: uuid.UUID | None
    state: str
    created: bool
    circuit_state: str
    message: str


class FormalityBatchRequest(ApiModel):
    province_code: str = Field(pattern=r"^\d{2}$")
    period_type: Literal["month", "quarter", "year"]
    year: int = Field(ge=2026, le=2200)
    period_value: int | None = None
    level: Literal["province", "ward"] | None = None
    field: str | None = None
    query: str | None = None
    include_internal: bool = True

    @model_validator(mode="after")
    def validate_period(self) -> "FormalityBatchRequest":
        PeriodSelection(self.period_type, self.year, self.period_value).validate_collectable()
        return self


class FormalityBatchResponse(ApiModel):
    id: uuid.UUID
    state: str
    province_code: str
    period_type: str
    year: int
    period_value: int | None
    filters: dict[str, Any]
    total_items: int
    available_items: int
    completed_items: int
    failed_items: int
    created_at: datetime
    updated_at: datetime


class ProvinceCollectionBatchResponse(ApiModel):
    id: uuid.UUID
    state: str
    period_type: str
    year: int
    period_value: int | None
    catalog_version: str
    total_items: int
    available_items: int
    completed_items: int
    failed_items: int
    error: dict[str, Any] | None
    created_at: datetime
    updated_at: datetime


class ProvinceCollectionBatchItemResponse(ApiModel):
    id: int
    batch_id: uuid.UUID
    position: int
    province_code: str
    province_name: str
    root_department_id: uuid.UUID
    state: str
    job_id: uuid.UUID | None
    error: dict[str, Any] | None
    created_at: datetime
    updated_at: datetime


class NationalSummaryResponse(ApiModel):
    id: uuid.UUID
    period_type: str
    year: int
    period_value: int | None
    department_type: str
    province_count: int
    raw_sha256: str
    captured_at: datetime
    created_at: datetime
