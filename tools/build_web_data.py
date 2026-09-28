"""Build the compact, fixture-backed dataset consumed by the M2 dashboard."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from qd766 import PeriodSelection, build_fixture_snapshot


PERIODS = (
    ("month-2026-08", "Tháng 8/2026", PeriodSelection("month", 2026, 8)),
    ("quarter-2026-03", "Quý III/2026", PeriodSelection("quarter", 2026, 3)),
    ("year-2026", "Năm 2026", PeriodSelection("year", 2026)),
)

GROUP_LABELS = {
    "transparency": "Công khai, minh bạch",
    "dvc-progress-tree": "Tiến độ giải quyết",
    "provide-online-tree": "Dịch vụ công trực tuyến",
    "dossier-digitized": "Số hóa hồ sơ",
    "handling-satisfaction": "Mức độ hài lòng",
    "formality-online-payment-tree": "Thanh toán trực tuyến",
}


def entity_dict(entity, *, include_detail: bool) -> dict:
    result = {
        "departmentId": entity.departmentId,
        "departmentName": entity.departmentName,
        "departmentType": entity.departmentType,
        "departmentLevel": entity.departmentLevel,
        "agencyLevel": entity.agencyLevel,
        "apiScore": entity.apiScore,
        "apiMaxScore": entity.apiMaxScore,
        "apiRatio": entity.apiRatio,
        "scoreSource": entity.scoreSource,
    }
    if include_detail:
        result["metrics"] = [asdict(metric) for metric in entity.metrics]
        result["parameters"] = entity.parameters
    return result


def snapshot_dict(snapshot) -> dict:
    datasets = []
    for dataset in snapshot.datasets:
        datasets.append(
            {
                "group": dataset.group,
                "label": GROUP_LABELS[dataset.group],
                "schemaKind": dataset.schemaKind,
                "formulaStatus": dataset.formulaStatus,
                "scorePolicy": dataset.scorePolicy,
                "root": entity_dict(dataset.root, include_detail=True),
                "children": [
                    entity_dict(child, include_detail=True)
                    for child in dataset.children
                ],
                "raw": asdict(dataset.raw),
                "capture": {
                    "capturedAt": "",
                    "httpStatus": 200,
                    "contentType": "application/json",
                    "bytes": 0,
                },
            }
        )
    return {
        "scope": snapshot.scope,
        "formalityId": snapshot.formalityId,
        "status": asdict(snapshot.status),
        "provinceAggregatedScore": snapshot.provinceAggregatedScore,
        "provinceAggregatedMaximum": snapshot.provinceAggregatedMaximum,
        "scorePolicy": snapshot.scorePolicy,
        "datasets": datasets,
        "delivery": {
            "result": "fixture",
            "capturedAt": "",
            "provisional": False,
            "stale": False,
            "message": "Dữ liệu kiểm thử tĩnh.",
        },
    }


def provisional(period: PeriodSelection) -> bool:
    current = date.today()
    if period.year != current.year:
        return period.year > current.year
    if period.type == "year":
        return True
    if period.type == "quarter":
        return period.value == ((current.month - 1) // 3) + 1
    return period.value == current.month


def build(fixtures: Path) -> dict:
    manifest = json.loads((fixtures / "manifest.m0.json").read_text(encoding="utf-8"))
    snapshots = {}
    periods = []
    for period_id, label, period in PERIODS:
        periods.append(
            {
                "id": period_id,
                "label": label,
                "type": period.type,
                "year": period.year,
                "value": period.value,
                "provisional": provisional(period),
            }
        )
        for scope in ("all", "formality"):
            snapshot = build_fixture_snapshot(fixtures, period, scope)
            if snapshot.status.state != "complete":
                raise ValueError(f"Incomplete fixture snapshot: {period_id}/{scope}")
            snapshots[f"{period_id}:{scope}"] = snapshot_dict(snapshot)
    first_snapshot = next(iter(snapshots.values()))
    first_dataset = first_snapshot["datasets"][0]
    root = first_dataset["root"]
    units = {
        root["departmentId"]: {
            "departmentId": root["departmentId"],
            "departmentName": root["departmentName"],
            "departmentType": root["departmentType"],
            "departmentLevel": "PROVINCE_TOTAL",
        }
    }
    for snapshot in snapshots.values():
        for dataset in snapshot["datasets"]:
            for entity in dataset["children"]:
                units.setdefault(
                    entity["departmentId"],
                    {
                        "departmentId": entity["departmentId"],
                        "departmentName": entity["departmentName"],
                        "departmentType": entity["departmentType"],
                        "departmentLevel": entity["departmentLevel"],
                    },
                )

    return {
        "schemaVersion": 1,
        "source": "QĐ766 M0 fixtures; API scores are authoritative",
        "province": manifest["province"],
        "formality": manifest["formality"],
        "periods": periods,
        "groupOrder": list(GROUP_LABELS),
        "groupLabels": GROUP_LABELS,
        "metricCatalog": [],
        "defaultUnitId": root["departmentId"],
        "units": list(units.values()),
        "snapshots": snapshots,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixtures", type=Path, default=ROOT / "tests/fixtures")
    parser.add_argument("--output", type=Path, default=ROOT / "web/data/snapshots.json")
    args = parser.parse_args()
    data = build(args.fixtures)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(data, ensure_ascii=False, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "output": str(args.output),
                "snapshots": len(data["snapshots"]),
                "periods": len(data["periods"]),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
