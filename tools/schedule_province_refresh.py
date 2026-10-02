#!/usr/bin/env python3
"""Schedule at most one circuit-protected nationwide detail refresh batch."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

from sqlalchemy import func, select

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from qd766.backend.config import Settings, load_environment_file
from qd766.backend.database import create_database_engine, create_session_factory
from qd766.backend.models import CollectionControl, ProvinceCollectionBatch, Snapshot
from qd766.backend.province_batches import create_province_batch
from qd766.backend.province_refresh import choose_detail_refresh_period, current_detail_periods
from qd766.province_roots import catalog_path, load_province_roots


def _catalog_version() -> str:
    path = catalog_path()
    raw = path.read_bytes()
    payload = json.loads(raw)
    generated = str(payload.get("generatedAt") or "unknown")
    return f"{generated}:{hashlib.sha256(raw).hexdigest()}"


def _period_key(period) -> tuple[str, int, int | None]:
    return period.type, period.year, period.value


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser()
    parser.add_argument("--interval-hours", type=float, default=72.0)
    parser.add_argument("--dry-run", action="store_true")
    arguments = parser.parse_args()
    if arguments.interval_hours <= 0:
        parser.error("--interval-hours must be positive")

    load_environment_file(ROOT / ".env")
    engine = create_database_engine(Settings.from_env())
    factory = create_session_factory(engine)
    # The reporting period follows the office machine's local calendar. This is
    # important during the first seven hours of a new month in Viet Nam.
    now = datetime.now().astimezone()
    try:
        with factory.begin() as session:
            control = session.get(CollectionControl, "dvcqg")
            if control is not None and control.circuit_state == "open":
                print(json.dumps({"state": "circuit-open"}))
                return 0

            latest_batch = session.scalar(
                select(ProvinceCollectionBatch)
                .order_by(ProvinceCollectionBatch.updated_at.desc())
                .limit(1)
            )
            if latest_batch is not None and latest_batch.state in {
                "queued",
                "running",
                "failed",
                "halted",
            }:
                state = (
                    "needs-review"
                    if latest_batch.state in {"failed", "halted"}
                    else "busy"
                )
                print(
                    json.dumps(
                        {
                            "state": state,
                            "batchId": str(latest_batch.id),
                            "batchState": latest_batch.state,
                        }
                    )
                )
                return 0

            roots = list(load_province_roots().values())
            root_ids = {root.root_department_id for root in roots}
            latest = {}
            for candidate in current_detail_periods(now):
                statement = select(
                    Snapshot.root_department_id, func.max(Snapshot.created_at)
                ).where(
                    Snapshot.state == "complete", Snapshot.scope == "all",
                    Snapshot.period_type == candidate.type,
                    Snapshot.year == candidate.year,
                    Snapshot.root_department_id.in_(root_ids),
                    Snapshot.period_value == candidate.value,
                ).group_by(Snapshot.root_department_id)
                captures = dict(session.execute(statement).all())
                # A batch's completion time cannot prove that its skipped
                # provinces have fresh data. Use the oldest latest snapshot.
                if root_ids.issubset(captures):
                    latest[_period_key(candidate)] = min(captures.values())
            period = choose_detail_refresh_period(
                now,
                latest,
                interval=timedelta(hours=arguments.interval_hours),
            )
            if period is None:
                print(json.dumps({"state": "fresh"}))
                return 0
            output = {
                "state": "planned" if arguments.dry_run else "queued",
                "periodType": period.type,
                "year": period.year,
                "periodValue": period.value,
                "intervalHours": arguments.interval_hours,
            }
            if not arguments.dry_run:
                refresh_key = (
                    f"auto:{period.type}:{period.year}:{period.value or 0}:"
                    f"{now.date().isoformat()}"
                )
                batch, created = create_province_batch(
                    session,
                    roots,
                    period,
                    catalog_version=_catalog_version(),
                    refresh_key=refresh_key,
                    fresh_after=now - timedelta(hours=arguments.interval_hours),
                )
                output.update(batchId=str(batch.id), created=created)
            print(json.dumps(output, ensure_ascii=False))
            return 0
    finally:
        engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
