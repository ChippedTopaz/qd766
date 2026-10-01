#!/usr/bin/env python3
"""Refresh versioned national summaries under the shared DVCQG lease."""

from __future__ import annotations

import argparse
import json
import os
import socket
import sys
import time
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from qd766.backend.config import Settings, load_environment_file
from qd766.backend.database import create_database_engine, create_session_factory
from qd766.backend.jobs import (
    acquire_collection_lease,
    open_collection_circuit,
    release_collection_lease,
)
from qd766.backend.national_summaries import store_national_summary
from qd766.collection import BrowserTransport, CollectionError, SafetyStop
from qd766.national_summary import collect_national_summary
from qd766.periods import PeriodSelection


def _current_periods(today: date) -> list[PeriodSelection]:
    return [
        PeriodSelection("month", today.year, today.month),
        PeriodSelection("quarter", today.year, (today.month - 1) // 3 + 1),
        PeriodSelection("year", today.year),
    ]


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser()
    parser.add_argument("--period-type", choices=("month", "quarter", "year"))
    parser.add_argument("--year", type=int)
    parser.add_argument("--period-value", type=int)
    parser.add_argument("--delay-seconds", type=float, default=5.0)
    arguments = parser.parse_args()
    if arguments.delay_seconds < 0:
        parser.error("--delay-seconds must be non-negative")
    if arguments.period_type:
        if arguments.year is None:
            parser.error("--year is required with --period-type")
        periods = [
            PeriodSelection(
                arguments.period_type,
                arguments.year,
                arguments.period_value,
            )
        ]
    elif arguments.year is not None or arguments.period_value is not None:
        parser.error("period arguments require --period-type")
    else:
        periods = _current_periods(date.today())

    load_environment_file(ROOT / ".env")
    engine = create_database_engine(Settings.from_env())
    factory = create_session_factory(engine)
    worker_id = f"national-summary:{socket.gethostname()}:{os.getpid()}"
    acquired = False
    results: list[dict] = []
    try:
        with factory.begin() as session:
            lease_state = acquire_collection_lease(
                session, worker_id, lease_seconds=1800
            )
        if lease_state != "acquired":
            print(json.dumps({"state": lease_state}, ensure_ascii=False))
            return 0
        acquired = True
        with BrowserTransport(timeout_seconds=45) as transport:
            for index, period in enumerate(periods):
                capture = collect_national_summary(period, transport)
                with factory.begin() as session:
                    snapshot, created = store_national_summary(session, capture)
                results.append(
                    {
                        "periodType": period.type,
                        "year": period.year,
                        "periodValue": period.value,
                        "provinceCount": snapshot.province_count,
                        "capturedAt": snapshot.captured_at.isoformat(),
                        "created": created,
                    }
                )
                if index < len(periods) - 1:
                    time.sleep(arguments.delay_seconds)
        with factory.begin() as session:
            release_collection_lease(session, worker_id)
        acquired = False
        print(
            json.dumps(
                {"state": "succeeded", "summaries": results},
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0
    except SafetyStop as error:
        detail = {
            "kind": "national-summary-safety-stop",
            "retryable": False,
            "message": str(error)[:500],
        }
        with factory.begin() as session:
            open_collection_circuit(
                session,
                reason="national-summary-safety-stop",
                detail=detail,
            )
        acquired = False
        print(json.dumps({"state": "halted", "error": detail}, ensure_ascii=False))
        return 2
    except CollectionError as error:
        print(
            json.dumps(
                {"state": "failed", "error": str(error)[:500]},
                ensure_ascii=False,
            )
        )
        return 1
    finally:
        if acquired:
            with factory.begin() as session:
                release_collection_lease(session, worker_id)
        engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
