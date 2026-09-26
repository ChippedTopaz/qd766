"""Loss-aware normalization for QĐ766 evaluation responses.

The API score is authoritative. Normalization never derives or replaces it.
Every endpoint-specific field remains available either as a metric, parameter,
dataset detail, or through the raw fixture reference.
"""

from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

METRIC_GROUPS = {
    "transparency",
    "handling-satisfaction",
    "dossier-digitized",
}

PARAMETER_GROUPS = {
    "dvc-progress-tree",
    "provide-online-tree",
    "formality-online-payment-tree",
}

ALL_GROUPS = METRIC_GROUPS | PARAMETER_GROUPS

IDENTITY_KEYS = {
    "stt",
    "departmentId",
    "departmentName",
    "departmentCode",
    "departmentType",
    "departmentLevel",
    "agencyLevel",
    "level",
}

SCORE_KEYS = {
    "totalScore",
    "score",
    "totalMaxScore",
    "maxScore",
    "ratio",
}


@dataclass(frozen=True)
class RawReference:
    path: str
    sha256: str


@dataclass
class NormalizedMetric:
    code: str
    name: str
    numerator: float | int | None
    denominator: float | int | None
    ratio: float | int | None
    apiScore: float | int | None
    apiMaxScore: float | int | None
    extras: dict[str, Any] = field(default_factory=dict)


@dataclass
class NormalizedEntity:
    departmentId: str
    departmentName: str
    departmentCode: str | None
    departmentType: str | None
    departmentLevel: str | None
    agencyLevel: str | None
    apiScore: float | int | None
    apiMaxScore: float | int | None
    apiRatio: float | int | None
    scoreSource: str
    formulaApplied: bool
    metrics: list[NormalizedMetric]
    parameters: dict[str, Any]
    metadata: dict[str, Any]


@dataclass
class NormalizedDataset:
    group: str
    schemaKind: str
    formulaStatus: str
    scorePolicy: str
    period: dict[str, Any]
    scope: str
    formalityId: str | None
    root: NormalizedEntity
    children: list[NormalizedEntity]
    details: dict[str, Any]
    raw: RawReference

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _api_score(record: dict[str, Any]) -> float | int | None:
    if "totalScore" in record:
        return record["totalScore"]
    return record.get("score")


def _api_max_score(record: dict[str, Any]) -> float | int | None:
    if "totalMaxScore" in record:
        return record["totalMaxScore"]
    return record.get("maxScore")


def _normalize_metric(metric: dict[str, Any]) -> NormalizedMetric:
    standard = {
        "code",
        "name",
        "numerator",
        "denominator",
        "ratio",
        "score",
        "maxScore",
    }
    return NormalizedMetric(
        code=metric["code"],
        name=metric["name"],
        numerator=metric.get("numerator"),
        denominator=metric.get("denominator"),
        ratio=metric.get("ratio"),
        apiScore=metric.get("score"),
        apiMaxScore=metric.get("maxScore"),
        extras=copy.deepcopy({key: value for key, value in metric.items() if key not in standard}),
    )


def _normalize_entity(record: dict[str, Any]) -> NormalizedEntity:
    metrics = [_normalize_metric(metric) for metric in record.get("metrics", [])]
    excluded = IDENTITY_KEYS | SCORE_KEYS | {"metrics"}
    parameters = copy.deepcopy(
        {key: value for key, value in record.items() if key not in excluded}
    )
    metadata = copy.deepcopy(
        {key: record[key] for key in IDENTITY_KEYS if key in record and key != "departmentId" and key != "departmentName"}
    )
    return NormalizedEntity(
        departmentId=record["departmentId"],
        departmentName=record["departmentName"],
        departmentCode=record.get("departmentCode"),
        departmentType=record.get("departmentType"),
        departmentLevel=record.get("departmentLevel", record.get("level")),
        agencyLevel=record.get("agencyLevel"),
        apiScore=_api_score(record),
        apiMaxScore=_api_max_score(record),
        apiRatio=record.get("ratio"),
        scoreSource="dvcqg-api",
        formulaApplied=False,
        metrics=metrics,
        parameters=parameters,
        metadata=metadata,
    )


def normalize_fixture(
    fixture_path: Path,
    *,
    fixtures_root: Path,
    group: str,
    period: dict[str, Any],
    scope: str,
    formality_id: str | None,
) -> NormalizedDataset:
    """Normalize one captured response without mutating the raw object."""

    if group not in ALL_GROUPS:
        raise ValueError(f"Unsupported group: {group}")
    raw_bytes = fixture_path.read_bytes()
    response = json.loads(raw_bytes)
    data = response["data"]
    metric_schema = group in METRIC_GROUPS
    root_key = "overview" if metric_schema else "parent"
    children_key = "evaluation" if metric_schema else "children"
    detail_keys = set(data) - {root_key, children_key}
    formula_status = (
        "metrics-returned-by-api"
        if metric_schema
        else "parameters-retained-no-recalculation"
    )
    return NormalizedDataset(
        group=group,
        schemaKind="metrics" if metric_schema else "parameters",
        formulaStatus=formula_status,
        scorePolicy="api-authoritative",
        period=copy.deepcopy(period),
        scope=scope,
        formalityId=formality_id,
        root=_normalize_entity(data[root_key]),
        children=[_normalize_entity(record) for record in data[children_key]],
        details=copy.deepcopy({key: data[key] for key in detail_keys}),
        raw=RawReference(
            path=fixture_path.relative_to(fixtures_root).as_posix(),
            sha256=hashlib.sha256(raw_bytes).hexdigest(),
        ),
    )
