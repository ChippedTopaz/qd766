from __future__ import annotations

from decimal import Decimal
from typing import Any

from .models import Dataset, Entity, Formality, Snapshot


GROUP_LABELS = {
    "transparency": "Công khai, minh bạch",
    "dvc-progress-tree": "Tiến độ giải quyết",
    "provide-online-tree": "Dịch vụ công trực tuyến",
    "dossier-digitized": "Số hóa hồ sơ",
    "handling-satisfaction": "Mức độ hài lòng",
    "formality-online-payment-tree": "Thanh toán trực tuyến",
}


def _number(value: Decimal | None) -> float | None:
    return float(value) if value is not None else None


def _period_id(snapshot: Snapshot) -> str:
    if snapshot.period_type == "year":
        return f"year-{snapshot.year}"
    return f"{snapshot.period_type}-{snapshot.year}-{snapshot.period_value:02d}"


def _period_label(snapshot: Snapshot) -> str:
    if snapshot.period_type == "month":
        return f"Tháng {snapshot.period_value}/{snapshot.year}"
    if snapshot.period_type == "quarter":
        return f"Quý {snapshot.period_value}/{snapshot.year}"
    return f"Năm {snapshot.year}"


def _entity(entity: Entity, *, include_detail: bool) -> dict[str, Any]:
    department = entity.department
    result: dict[str, Any] = {
        "departmentId": str(entity.department_id),
        "departmentName": department.name,
        "departmentType": department.department_type,
        "departmentLevel": department.department_level,
        "agencyLevel": department.agency_level,
        "apiScore": _number(entity.api_score),
        "apiMaxScore": _number(entity.api_max_score),
        "apiRatio": _number(entity.api_ratio),
        "scoreSource": entity.score_source,
    }
    if include_detail:
        result["metrics"] = [
            {
                "code": metric.code,
                "name": metric.name,
                "numerator": _number(metric.numerator),
                "denominator": _number(metric.denominator),
                "ratio": _number(metric.ratio),
                "apiScore": _number(metric.api_score),
                "apiMaxScore": _number(metric.api_max_score),
                "extras": metric.extras,
            }
            for metric in entity.metrics
        ]
        result["parameters"] = entity.parameters
    return result


def _dataset(dataset: Dataset) -> dict[str, Any]:
    root = next(entity for entity in dataset.entities if entity.entity_kind == "root")
    children = [entity for entity in dataset.entities if entity.entity_kind == "child"]
    return {
        "group": dataset.group_name,
        "label": GROUP_LABELS.get(dataset.group_name, dataset.group_name),
        "schemaKind": dataset.schema_kind,
        "formulaStatus": dataset.formula_status,
        "scorePolicy": dataset.score_policy,
        "root": _entity(root, include_detail=True),
        "children": [_entity(entity, include_detail=False) for entity in children],
        "raw": {"path": dataset.raw_path, "sha256": dataset.raw_sha256},
    }


def dashboard_payload(
    snapshots: list[Snapshot],
    formality: Formality | None,
) -> dict[str, Any]:
    periods: dict[str, dict[str, Any]] = {}
    payload_snapshots: dict[str, dict[str, Any]] = {}
    for snapshot in snapshots:
        period_id = _period_id(snapshot)
        periods.setdefault(
            period_id,
            {
                "id": period_id,
                "label": _period_label(snapshot),
                "type": snapshot.period_type,
                "year": snapshot.year,
                **(
                    {"month": snapshot.period_value}
                    if snapshot.period_type == "month"
                    else {"quarter": snapshot.period_value}
                    if snapshot.period_type == "quarter"
                    else {}
                ),
            },
        )
        payload_snapshots[f"{period_id}:{snapshot.scope}"] = {
            "scope": snapshot.scope,
            "formalityId": str(snapshot.formality_id) if snapshot.formality_id else None,
            "status": snapshot.status_detail,
            "provinceAggregatedScore": _number(snapshot.province_aggregated_score),
            "provinceAggregatedMaximum": _number(snapshot.province_aggregated_maximum),
            "scorePolicy": snapshot.policy,
            "datasets": [_dataset(dataset) for dataset in snapshot.datasets],
        }

    root = snapshots[0].root_department
    ordered_periods = sorted(
        periods.values(),
        key=lambda item: (
            -item["year"],
            {"month": 0, "quarter": 1, "year": 2}[item["type"]],
            -(item.get("month") or item.get("quarter") or 0),
        ),
    )
    return {
        "schemaVersion": 1,
        "source": "PostgreSQL snapshots; API scores are authoritative",
        "province": {"id": str(root.id), "name": root.name},
        "formality": {
            "id": str(formality.id) if formality else None,
            "code": formality.code if formality else "",
            "name": formality.name if formality else "Không có dữ liệu TTHC",
        },
        "periods": ordered_periods,
        "groupOrder": list(GROUP_LABELS),
        "groupLabels": GROUP_LABELS,
        "snapshots": payload_snapshots,
    }
