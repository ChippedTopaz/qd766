"""Validate all six M1 fixture snapshot combinations and write a compact report."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from qd766 import PeriodSelection, build_fixture_snapshot


def validate(root: Path) -> dict:
    fixtures = root / "tests/fixtures"
    snapshots = []
    for period_type, value in (("month", 8), ("quarter", 3), ("year", None)):
        for scope in ("all", "formality"):
            snapshot = build_fixture_snapshot(
                fixtures, PeriodSelection(period_type, 2026, value), scope
            )
            snapshots.append(
                {
                    "period": snapshot.period,
                    "scope": scope,
                    "state": snapshot.status.state,
                    "loadedGroups": snapshot.status.loadedGroups,
                    "unsupportedGroups": snapshot.status.unsupportedGroups,
                    "provinceAggregatedScore": snapshot.provinceAggregatedScore,
                    "provinceAggregatedMaximum": snapshot.provinceAggregatedMaximum,
                    "rootEntities": len(snapshot.datasets),
                    "childEntities": sum(len(dataset.children) for dataset in snapshot.datasets),
                    "rawReferences": [dataset.raw.path for dataset in snapshot.datasets],
                }
            )
    failures = [item for item in snapshots if item["state"] != "complete"]
    all_scope = [item for item in snapshots if item["scope"] == "all"]
    all_maximums_are_100 = all(item["provinceAggregatedMaximum"] == 100 for item in all_scope)
    return {
        "result": "PASS" if not failures and all_maximums_are_100 else "FAIL",
        "scope": (
            "Offline M1 normalization, completeness and API-score aggregation "
            "against captured M0 fixtures only"
        ),
        "scoreAuthority": "DVCQG response score/totalScore",
        "formulaPolicy": "API scores are authoritative; explanatory formulas are versioned and checked",
        "snapshots": snapshots,
        "remainingGaps": [
            "METRICS maxScore còn trống tại STT 7, 8, 9, 10, 18",
            "Chưa kiểm chứng crawler production và các tỉnh ngoài Phú Thọ",
        ],
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    report = validate(args.root)
    output = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.report:
        with args.report.open("w", encoding="utf-8", newline="\n") as stream:
            stream.write(output)
    print(json.dumps(report, ensure_ascii=True, indent=2))
    raise SystemExit(0 if report["result"] == "PASS" else 1)
