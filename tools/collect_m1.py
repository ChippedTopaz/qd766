"""Plan or execute one safe, sequential M1 collection snapshot."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from qd766 import (
    PeriodSelection,
    build_collected_snapshot,
    collect_snapshot,
    plan_evaluation_requests,
)
from qd766.collection import UrllibTransport


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--period", choices=["month", "quarter", "year"], required=True)
    parser.add_argument("--year", type=int, required=True)
    parser.add_argument("--value", type=int)
    parser.add_argument("--root-department-id", required=True)
    parser.add_argument("--formality-id")
    parser.add_argument("--output", type=Path)
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Send the planned requests. Without this flag the command only prints the plan.",
    )
    args = parser.parse_args()

    try:
        period = PeriodSelection(args.period, args.year, args.value)
        period.validate_collectable()
    except ValueError as error:
        parser.error(str(error))
    plan = plan_evaluation_requests(
        period, args.root_department_id, args.formality_id
    )
    if not args.execute:
        print(
            json.dumps(
                {
                    "mode": "plan-only",
                    "requests": [request.__dict__ for request in plan],
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0
    if args.output is None:
        parser.error("--output is required with --execute")

    manifest = collect_snapshot(
        plan,
        period=period,
        output_dir=args.output,
        transport=UrllibTransport(),
    )
    snapshot = build_collected_snapshot(args.output)
    normalized_path = args.output / "normalized.json"
    normalized_path.write_text(
        json.dumps(snapshot.to_dict(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "status": manifest["status"],
                "manifest": str(args.output / "manifest.json"),
                "normalized": str(normalized_path),
                "provinceAggregatedScore": snapshot.provinceAggregatedScore,
                "provinceAggregatedMaximum": snapshot.provinceAggregatedMaximum,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
