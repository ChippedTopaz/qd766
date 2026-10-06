from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

from qd766.province_catalog import PROVINCES

from .models import Dataset, Entity, Formality, NationalSummarySnapshot, Snapshot


GROUP_LABELS = {
    "transparency": "Công khai, minh bạch",
    "dvc-progress-tree": "Tiến độ giải quyết",
    "provide-online-tree": "Dịch vụ công trực tuyến",
    "dossier-digitized": "Số hóa hồ sơ",
    "handling-satisfaction": "Mức độ hài lòng",
    "formality-online-payment-tree": "Thanh toán trực tuyến",
}
NATIONAL_GROUP_CODES = {
    "transparency": "CKMB",
    "dvc-progress-tree": "TDGQ",
    "provide-online-tree": "CLGQ",
    "dossier-digitized": "MDSH",
    "handling-satisfaction": "MDHL",
    "formality-online-payment-tree": "TTTT",
}
NATIONAL_GROUP_MAXIMUMS = {
    "transparency": 18.0,
    "dvc-progress-tree": 20.0,
    "provide-online-tree": 12.0,
    "dossier-digitized": 22.0,
    "handling-satisfaction": 18.0,
    "formality-online-payment-tree": 10.0,
}
REPORTING_START_YEAR = 2026


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


def _is_provisional(snapshot: Snapshot, today: date | None = None) -> bool:
    current = today or date.today()
    if snapshot.year != current.year:
        return snapshot.year > current.year
    if snapshot.period_type == "year":
        return True
    if snapshot.period_type == "quarter":
        return snapshot.period_value == ((current.month - 1) // 3) + 1
    return snapshot.period_value == current.month


def _national_summary_is_stale(
    summary: NationalSummarySnapshot,
    now: datetime | None = None,
) -> bool:
    current = now or datetime.now(timezone.utc)
    from .province_refresh import VIETNAM, daily_fresh_after
    current_date = current.astimezone(VIETNAM).date()
    is_open = summary.year == current_date.year and (
        summary.period_type == "year"
        or (
            summary.period_type == "month"
            and summary.period_value == current_date.month
        )
        or (
            summary.period_type == "quarter"
            and summary.period_value == ((current_date.month - 1) // 3) + 1
        )
    )
    if not is_open:
        return False
    captured_at = summary.captured_at
    if captured_at.tzinfo is None:
        captured_at = captured_at.replace(tzinfo=timezone.utc)
    return captured_at < daily_fresh_after(current)


def _detail_snapshot_is_stale(
    snapshot: Snapshot,
    now: datetime | None = None,
    max_age: timedelta | None = None,
) -> bool:
    """Only open reporting periods expire; completed periods stay immutable."""
    current = now or datetime.now(timezone.utc)
    from .province_refresh import VIETNAM, daily_fresh_after
    if not _is_provisional(snapshot, current.astimezone(VIETNAM).date()):
        return False
    captured_at = snapshot.created_at
    if captured_at.tzinfo is None:
        captured_at = captured_at.replace(tzinfo=timezone.utc)
    return captured_at < (current-max_age if max_age is not None else daily_fresh_after(current))


def _available_periods(snapshots: list[Snapshot], today: date | None = None) -> list[dict[str, Any]]:
    current = today or date.today()
    periods: dict[str, dict[str, Any]] = {}
    for year in range(REPORTING_START_YEAR, current.year + 1):
        last_month = current.month if year == current.year else 12
        last_quarter = ((current.month - 1) // 3) + 1 if year == current.year else 4
        for month in range(1, last_month + 1):
            period_id = f"month-{year}-{month:02d}"
            periods[period_id] = {
                "id": period_id,
                "label": f"Tháng {month}/{year}",
                "type": "month",
                "year": year,
                "value": month,
                "provisional": year == current.year and month == current.month,
            }
        for quarter in range(1, last_quarter + 1):
            period_id = f"quarter-{year}-{quarter:02d}"
            periods[period_id] = {
                "id": period_id,
                "label": f"Quý {quarter}/{year}",
                "type": "quarter",
                "year": year,
                "value": quarter,
                "provisional": year == current.year and quarter == last_quarter,
            }
        period_id = f"year-{year}"
        periods[period_id] = {
            "id": period_id,
            "label": f"Năm {year}",
            "type": "year",
            "year": year,
            "value": None,
            "provisional": year == current.year,
        }

    # Preserve any historical database period outside the generated range.
    for snapshot in snapshots:
        period_id = _period_id(snapshot)
        periods[period_id] = {
            "id": period_id,
            "label": _period_label(snapshot),
            "type": snapshot.period_type,
            "year": snapshot.year,
            "value": snapshot.period_value,
            "provisional": _is_provisional(snapshot, current),
        }
    return sorted(
        periods.values(),
        key=lambda item: (
            -item["year"],
            {"month": 0, "quarter": 1, "year": 2}[item["type"]],
            -(item["value"] or 0),
        ),
    )


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
    else:
        result["metrics"] = []
        # Retain volume history for period comparisons without transporting all
        # historical component details at initial load.
        result["parameters"] = {key: value for key, value in entity.parameters.items() if key == "totalReceived"}
    return result


def _dataset(dataset: Dataset, *, include_detail: bool = True) -> dict[str, Any]:
    root = next(entity for entity in dataset.entities if entity.entity_kind == "root")
    children = [entity for entity in dataset.entities if entity.entity_kind == "child"]
    return {
        "group": dataset.group_name,
        "label": GROUP_LABELS.get(dataset.group_name, dataset.group_name),
        "schemaKind": dataset.schema_kind,
        "formulaStatus": dataset.formula_status,
        "scorePolicy": dataset.score_policy,
        "root": _entity(root, include_detail=include_detail),
        # The analytical frontend needs metrics/parameters for the selected child,
        # not only for the provincial root. Keep one canonical response contract.
        "children": [_entity(entity, include_detail=include_detail) for entity in children],
        "raw": {"path": dataset.raw_path, "sha256": dataset.raw_sha256},
        "capture": {
            "capturedAt": dataset.snapshot.created_at.isoformat(),
            "httpStatus": 200,
            "contentType": "application/json",
            "bytes": 0,
        },
    }


def snapshot_payload(
    snapshot: Snapshot,
    national_summary: NationalSummarySnapshot | None = None,
    *, include_detail: bool = True,
) -> dict[str, Any]:
    details_stale = _detail_snapshot_is_stale(snapshot)
    result = {
        "scope": snapshot.scope,
        "formalityId": str(snapshot.formality_id) if snapshot.formality_id else None,
        "status": snapshot.status_detail,
        "provinceAggregatedScore": _number(snapshot.province_aggregated_score),
        "provinceAggregatedMaximum": _number(snapshot.province_aggregated_maximum),
        "scorePolicy": snapshot.policy,
        "datasets": [_dataset(dataset, include_detail=include_detail) for dataset in snapshot.datasets],
        "delivery": {
            "result": "database",
            "capturedAt": snapshot.created_at.isoformat(),
            "detailsCapturedAt": snapshot.created_at.isoformat(),
            "provisional": _is_provisional(snapshot),
            "stale": details_stale,
            "summaryStale": False,
            "detailsStale": details_stale,
            "message": (
                "Dữ liệu chi tiết của kỳ đang diễn ra đã quá 72 giờ; hệ thống "
                "đang chờ lượt làm mới an toàn tiếp theo."
                if details_stale
                else "Dữ liệu lấy từ PostgreSQL trên máy chủ QD766."
            ),
        },
    }
    if not include_detail:
        result["detailsLoaded"] = False
    if national_summary is not None and snapshot.scope == "all":
        row = next(
            (
                item
                for item in national_summary.response_data.get("evaluation", [])
                if item.get("departmentId") == str(snapshot.root_department_id)
            ),
            None,
        )
        if row is not None:
            group_scores = row.get("groupScores", {})
            for dataset in result["datasets"]:
                score = group_scores.get(NATIONAL_GROUP_CODES.get(dataset["group"]))
                if score is None:
                    continue
                dataset["root"]["apiScore"] = float(score)
                maximum = dataset["root"].get("apiMaxScore")
                dataset["root"]["apiRatio"] = (
                    round(float(score) / float(maximum) * 100, 2)
                    if maximum
                    else None
                )
                dataset["root"]["scoreSource"] = "dvcqg-national-summary"
            result["provinceAggregatedScore"] = float(row["totalScore"])
            result["provinceAggregatedMaximum"] = 100.0
            summary_stale = _national_summary_is_stale(national_summary)
            stale = summary_stale or details_stale
            if summary_stale and details_stale:
                message = (
                    "Bản tổng hợp toàn quốc đã quá 2 giờ và dữ liệu chi tiết đã "
                    "quá 72 giờ; hệ thống đang chờ các lượt làm mới an toàn tiếp theo."
                )
            elif summary_stale:
                message = (
                    "Bản tổng hợp toàn quốc đã quá 2 giờ; hệ thống đang chờ chu kỳ "
                    "cập nhật an toàn tiếp theo."
                )
            elif details_stale:
                message = (
                    "Điểm tỉnh và xếp hạng đã được cập nhật; dữ liệu chi tiết của "
                    "kỳ đang diễn ra đã quá 72 giờ và đang chờ lượt làm mới tiếp theo."
                )
            else:
                message = (
                    "Điểm tỉnh và xếp hạng lấy từ bản tổng hợp toàn quốc mới nhất; "
                    "chi tiết chỉ tiêu dùng snapshot phân tích gần nhất."
                )
            result["delivery"] = {
                "result": "national-summary",
                "capturedAt": national_summary.captured_at.isoformat(),
                "detailsCapturedAt": snapshot.created_at.isoformat(),
                "provisional": _is_provisional(snapshot),
                "stale": stale,
                "summaryStale": summary_stale,
                "detailsStale": details_stale,
                "message": message,
            }
    return result


def summary_only_snapshot(summary: NationalSummarySnapshot, root_id: str) -> dict[str, Any] | None:
    """Adapt saved national scores without inventing component or child data."""
    row = next((item for item in summary.response_data.get("evaluation", [])
                if str(item.get("departmentId")) == str(root_id)), None)
    if row is None:
        return None
    scores = row.get("groupScores", {})
    if any(scores.get(code) is None for code in NATIONAL_GROUP_CODES.values()):
        return None
    captured = summary.captured_at.isoformat()
    stale = _national_summary_is_stale(summary)
    datasets = []
    for group, code in NATIONAL_GROUP_CODES.items():
        score, maximum = float(scores[code]), NATIONAL_GROUP_MAXIMUMS[group]
        datasets.append({
            "group": group, "label": GROUP_LABELS[group], "schemaKind": "parameters",
            "formulaStatus": "summary-only", "scorePolicy": "api-authoritative",
            "root": {"departmentId": str(root_id), "departmentName": row["departmentName"],
                "departmentType": "ADMINISTRATIVE_UNIT", "departmentLevel": "PROVINCE_TOTAL",
                "agencyLevel": None, "apiScore": score, "apiMaxScore": maximum,
                "apiRatio": round(score / maximum * 100, 2),
                "scoreSource": "dvcqg-national-summary", "metrics": [], "parameters": {}},
            "children": [], "raw": {"path": "", "sha256": summary.raw_sha256},
            "capture": {"capturedAt": captured, "httpStatus": 200,
                "contentType": "application/json", "bytes": 0},
        })
    return {"scope": "all", "formalityId": None, "status": {"state": "complete",
            "requiredGroups": list(GROUP_LABELS), "loadedGroups": list(GROUP_LABELS),
            "unsupportedGroups": [], "missingGroups": []},
        "provinceAggregatedScore": float(row["totalScore"]), "provinceAggregatedMaximum": 100.0,
        "scorePolicy": {"source": "national-summary", "detailsAvailable": False},
        "datasets": datasets, "delivery": {"result": "national-summary", "capturedAt": captured,
            "detailsCapturedAt": None, "detailsAvailable": False,
            "provisional": _is_provisional(summary), "summaryStale": stale,
            "detailsStale": False, "stale": stale,
            "message": "Có điểm tổng hợp sáu nhóm của tỉnh; chưa có số liệu thành phần hoặc điểm đơn vị trực thuộc cho kỳ này."}}


def dashboard_payload(
    snapshots: list[Snapshot],
    formality: Formality | None,
    national_summaries: dict[
        tuple[str, int, int | None], NationalSummarySnapshot
    ] | None = None,
    *, detail_snapshot_ids: set | None = None,
) -> dict[str, Any]:
    payload_snapshots: dict[str, dict[str, Any]] = {}
    for snapshot in snapshots:
        period_id = _period_id(snapshot)
        summary = (national_summaries or {}).get(
            (snapshot.period_type, snapshot.year, snapshot.period_value)
        )
        payload_snapshots[f"{period_id}:{snapshot.scope}"] = snapshot_payload(
            snapshot, summary, include_detail=detail_snapshot_ids is None or snapshot.id in detail_snapshot_ids
        )

    root = snapshots[0].root_department
    root_name = root.name or ""
    province_code = next(
        (
            code
            for code, (name, _) in PROVINCES.items()
            if name.casefold() in root_name.casefold()
        ),
        None,
    )
    for key, summary in (national_summaries or {}).items():
        snapshot_key = f"{_period_id(summary)}:all"
        if snapshot_key not in payload_snapshots:
            item = summary_only_snapshot(summary, str(root.id))
            if item is not None:
                payload_snapshots[snapshot_key] = item
    ordered_periods = _available_periods([*snapshots, *(national_summaries or {}).values()])
    units: dict[str, dict[str, Any]] = {
        str(root.id): {
            "departmentId": str(root.id),
            "departmentName": root.name,
            "departmentType": root.department_type,
            "departmentLevel": "PROVINCE_TOTAL",
        }
    }
    for snapshot in snapshots:
        for dataset in snapshot.datasets:
            for entity in dataset.entities:
                if entity.entity_kind != "child":
                    continue
                department = entity.department
                units.setdefault(
                    str(department.id),
                    {
                        "departmentId": str(department.id),
                        "departmentName": department.name,
                        "departmentType": department.department_type,
                        "departmentLevel": department.department_level,
                    },
                )

    return {
        "schemaVersion": 1,
        "source": "PostgreSQL snapshots; API scores are authoritative",
        "province": {"id": str(root.id), "name": root.name, "code": province_code},
        "formality": {
            "id": str(formality.id) if formality else None,
            "code": formality.code if formality else "",
            "name": formality.name if formality else "Không có dữ liệu TTHC",
        },
        "periods": ordered_periods,
        "groupOrder": list(GROUP_LABELS),
        "groupLabels": GROUP_LABELS,
        "metricCatalog": [],
        "defaultUnitId": str(root.id),
        "units": list(units.values()),
        "snapshots": payload_snapshots,
    }
