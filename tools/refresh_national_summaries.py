#!/usr/bin/env python3
"""Refresh versioned national summaries under the shared DVCQG lease."""

from __future__ import annotations

import argparse
import json
import os
import socket
import sys
import time
from contextlib import nullcontext
from datetime import datetime, timedelta, timezone
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
from qd766.backend.national_summaries import latest_national_summary, store_national_summary
from qd766.collection import BrowserTransport, UrllibTransport, CollectionError, SafetyStop
from qd766.national_summary import collect_national_summary
from qd766.periods import PeriodSelection


def _current_periods(now: datetime) -> list[PeriodSelection]:
    return [
        PeriodSelection("month", now.year, now.month),
        PeriodSelection("quarter", now.year, (now.month - 1) // 3 + 1),
        PeriodSelection("year", now.year),
    ]


def _scheduled_period(now: datetime, *, year_available: bool) -> PeriodSelection:
    if not year_available or now.hour % 2 == 0:
        return PeriodSelection("year", now.year)
    if now.hour % 4 == 1:
        return PeriodSelection("month", now.year, now.month)
    return PeriodSelection("quarter", now.year, (now.month - 1) // 3 + 1)


def _missing_closed_periods(session, year: int, now: datetime) -> list[PeriodSelection]:
    if year > now.year:
        raise ValueError("Cannot backfill a future year")
    month_count = 12 if year < now.year else now.month - 1
    quarter_count = 4 if year < now.year else (now.month - 1) // 3
    candidates = [PeriodSelection("month", year, value) for value in range(1, month_count + 1)]
    candidates += [PeriodSelection("quarter", year, value) for value in range(1, quarter_count + 1)]
    return [period for period in candidates if latest_national_summary(session, period) is None]


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser()
    parser.add_argument("--period-type", choices=("month", "quarter", "year"))
    parser.add_argument("--year", type=int)
    parser.add_argument("--period-value", type=int)
    parser.add_argument("--all-current", action="store_true")
    parser.add_argument("--backfill-missing-year", type=int)
    parser.add_argument("--refresh-all-year", type=int, help="Refresh every available month/quarter/year, including existing summaries")
    parser.add_argument("--daily-policy", action="store_true", help="Open periods daily; closed periods only if not observed after close")
    parser.add_argument("--transport", choices=("browser", "urllib"), default="browser")
    parser.add_argument("--wait-for-lease-seconds", type=int, default=0)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--max-periods", type=int, default=12)
    parser.add_argument("--delay-seconds", type=float, default=5.0)
    arguments = parser.parse_args()
    if arguments.daily_policy and (arguments.refresh_all_year is not None or arguments.period_type or arguments.all_current or arguments.year is not None or arguments.period_value is not None or arguments.backfill_missing_year is not None):
        parser.error('--daily-policy cannot be combined with another period selector')
    if not 0 <= arguments.wait_for_lease_seconds <= 600:
        parser.error("--wait-for-lease-seconds must be between 0 and 600")
    if arguments.refresh_all_year is not None and (arguments.period_type or arguments.all_current or arguments.year is not None or arguments.period_value is not None or arguments.backfill_missing_year is not None):
        parser.error("--refresh-all-year cannot be combined with another period selector")
    if arguments.delay_seconds < 0:
        parser.error("--delay-seconds must be non-negative")
    if not 1 <= arguments.max_periods <= 12:
        parser.error("--max-periods must be between 1 and 12")
    if arguments.backfill_missing_year is not None and (arguments.period_type or arguments.all_current or arguments.year is not None or arguments.period_value is not None):
        parser.error("--backfill-missing-year cannot be combined with another period selector")
    now = datetime.now(timezone(timedelta(hours=7)))
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
    elif arguments.all_current:
        periods = _current_periods(now)
    else:
        periods = None

    load_environment_file(ROOT / ".env")
    engine = create_database_engine(Settings.from_env())
    factory = create_session_factory(engine)
    if arguments.daily_policy:
        from qd766.backend.province_refresh import daily_refresh_candidates, due_daily_periods
        with factory() as session:
            latest={}
            for period in daily_refresh_candidates(now):
                stored=latest_national_summary(session,period)
                if stored is not None:
                    latest[(period.type,period.year,period.value)]=stored.captured_at
            periods=due_daily_periods(now,latest)
        arguments.delay_seconds=max(arguments.delay_seconds,0.4)
    elif arguments.refresh_all_year is not None:
        from queue_full_default_refresh import refresh_periods
        periods = refresh_periods(arguments.refresh_all_year, now)
        arguments.delay_seconds = max(arguments.delay_seconds, 30.0)
    elif arguments.backfill_missing_year is not None:
        with factory() as session:
            periods = _missing_closed_periods(session, arguments.backfill_missing_year, now)[:arguments.max_periods]
        # Conservative spacing for manual historical batches; no retries.
        arguments.delay_seconds = max(arguments.delay_seconds, 30.0)
    elif periods is None:
        # Hourly task: checking only one rotating period left month/quarter
        # unobserved for four hours despite a two-hour freshness policy.
        periods = _current_periods(now)
    if arguments.dry_run or not periods:
        print(json.dumps({"state": "planned" if periods else "nothing-missing", "periods": [
            {"periodType": period.type, "year": period.year, "periodValue": period.value}
            for period in periods], "delaySeconds": arguments.delay_seconds}, ensure_ascii=False))
        engine.dispose()
        return 0
    worker_id = f"national-summary:{socket.gethostname()}:{os.getpid()}"
    acquired = False
    results: list[dict] = []
    try:
        wait_deadline = time.monotonic() + arguments.wait_for_lease_seconds
        while True:
            with factory.begin() as session:
                lease_state = acquire_collection_lease(
                    session, worker_id, lease_seconds=1800
                )
            if lease_state != "busy" or time.monotonic() >= wait_deadline:
                break
            time.sleep(5)
        if lease_state != "acquired":
            print(json.dumps({"state": lease_state}, ensure_ascii=False))
            return 0
        acquired = True
        transport_context = (BrowserTransport(timeout_seconds=45) if arguments.transport == "browser"
                             else nullcontext(UrllibTransport(timeout_seconds=45)))
        with transport_context as transport:
            for index, period in enumerate(periods):
                # Re-check circuit and refresh the shared lease before each call.
                with factory.begin() as session:
                    lease_state = acquire_collection_lease(session, worker_id, lease_seconds=1800)
                if lease_state != "acquired":
                    print(json.dumps({"state": lease_state, "summaries": results}, ensure_ascii=False))
                    return 0
                capture = collect_national_summary(period, transport)
                with factory.begin() as session:
                    snapshot, created = store_national_summary(session, capture)
                results.append(
                    {
                        "periodType": period.type,
                        "year": period.year,
                        "periodValue": period.value,
                        "provinceCount": snapshot.province_count,
                        "completenessState": snapshot.completeness_state,
                        "groupCount": snapshot.group_count,
                        "capturedAt": snapshot.captured_at.isoformat(),
                        "created": created,
                    }
                )
                print(json.dumps({"state": "period-saved", **results[-1]}, ensure_ascii=False), flush=True)
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
