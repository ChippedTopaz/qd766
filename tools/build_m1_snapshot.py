"""Build a normalized snapshot from the captured M0 fixtures."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from qd766 import PeriodSelection, build_fixture_snapshot


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--period", choices=["month", "quarter", "year"], required=True)
    parser.add_argument("--year", type=int, default=2026)
    parser.add_argument("--value", type=int)
    parser.add_argument("--scope", choices=["all", "formality"], default="all")
    parser.add_argument("--fixtures", type=Path, default=ROOT / "tests/fixtures")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    period = PeriodSelection(args.period, args.year, args.value)
    snapshot = build_fixture_snapshot(args.fixtures, period, args.scope)
    output = json.dumps(snapshot.to_dict(), ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.write_text(output, encoding="utf-8")
    else:
        print(output, end="")
    return 0 if snapshot.status.state == "complete" else 1


if __name__ == "__main__":
    raise SystemExit(main())
