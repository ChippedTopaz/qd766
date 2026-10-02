"""Office inventory: SELECT-only transaction; never enqueue or contact DVCQG."""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import select, text
from sqlalchemy.orm import Session, selectinload

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from qd766.backend.config import Settings, load_environment_file
from qd766.backend.database import create_database_engine
from qd766.backend.dashboard import GROUP_LABELS
from qd766.backend.models import Dataset, Department, Entity, Metric, NationalSummarySnapshot, Snapshot
from qd766.national_summary import _validate_data
from qd766.collection import CollectionError
from qd766.province_roots import load_province_roots


def period_key(row):
    return (row.period_type, row.year, row.period_value)


def previous(key):
    kind, year, value = key
    if kind == "year":
        return (kind, year - 1, None)
    last = 12 if kind == "month" else 4
    return (kind, year, value - 1) if value > 1 else (kind, year - 1, last)


def label(key):
    kind, year, value = key
    return f"{kind}-{year}" + (f"-{value:02d}" if value is not None else "")


def aware(value):
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def next_period_start(key):
    kind, year, value = key
    month = value + 1 if kind == "month" else value * 3 + 1 if kind == "quarter" else 13
    if month == 13:
        year, month = year + 1, 1
    return datetime(year, month, 1, tzinfo=timezone(timedelta(hours=7)))


def inventory(db, now):
    groups = set(GROUP_LABELS)
    local_date = now.astimezone(timezone(timedelta(hours=7))).date()
    current = {("year", local_date.year, None), ("month", local_date.year, local_date.month),
               ("quarter", local_date.year, (local_date.month - 1) // 3 + 1)}
    roots = load_province_roots()
    names = {str(item.root_department_id): item.province_name for item in roots.values()}
    national = {}
    for row in db.scalars(select(NationalSummarySnapshot).order_by(NationalSummarySnapshot.captured_at)):
        national[period_key(row)] = row
    snapshots = {}
    query = select(Snapshot).where(Snapshot.scope == "all").order_by(Snapshot.created_at).options(
        selectinload(Snapshot.datasets).selectinload(Dataset.entities).selectinload(Entity.department))
    for row in db.scalars(query):
        snapshots[(period_key(row), str(row.root_department_id))] = row
    metric_entities = set(db.scalars(select(Metric.entity_id).distinct()))
    detail = defaultdict(list)
    for (key, root_id), row in snapshots.items():
        scored = set()
        coverage = {}
        by_level = {"PROVINCE": defaultdict(set), "COMMUNE": defaultdict(set)}
        agency_names = {}
        for dataset in row.datasets:
            root = next((item for item in dataset.entities if item.entity_kind == "root"), None)
            if root is not None and root.api_score is not None:
                scored.add(dataset.group_name)
            children = [item for item in dataset.entities if item.entity_kind == "child"]
            coverage[dataset.group_name] = {
                "childRows": len(children), "childScores": sum(item.api_score is not None for item in children),
                "childMetrics": sum(item.id in metric_entities for item in children),
                "childParameters": sum(bool(item.parameters) for item in children)}
            for item in children:
                level = item.department.department_level
                agency_names[str(item.department_id)] = item.department.name
                if level in by_level and item.api_score is not None:
                    by_level[level][str(item.department_id)].add(dataset.group_name)
        detail[key].append({"province": names.get(root_id) or row.root_department.name or root_id,
            "rootId": root_id, "state": row.state, "scoreGroups": len(groups & scored),
            "missingScoreGroups": sorted(groups - scored), "capturedAt": aware(row.created_at).isoformat(),
            "stale": key in current and aware(row.created_at) < now - timedelta(hours=72),
            "closedButCapturedBeforeEnd": now >= next_period_start(key) and aware(row.created_at) < next_period_start(key),
            "priorAvailable": (previous(key), root_id) in snapshots,
            "agencies": {level: {"withAnyScore": len(units),
                "withSixScores": sum(groups <= values for values in units.values())}
                for level, units in by_level.items()},
            "incompleteAgencies": [{"name": agency_names[unit_id], "level": level,
                "missingGroups": sorted(groups - values)} for level, units in by_level.items()
                for unit_id, values in units.items() if not groups <= values],
            "groups": coverage})
    keys = set(national) | set(detail)
    keys |= {("year", local_date.year, None)}
    keys |= {("month", local_date.year, value) for value in range(1, local_date.month + 1)}
    keys |= {("quarter", local_date.year, value) for value in range(1, (local_date.month - 1) // 3 + 2)}
    rows = []
    for key in sorted(keys, key=lambda key: (key[1], {"month": 0, "quarter": 1, "year": 2}[key[0]], key[2] or 0)):
        summary = national.get(key)
        valid = False
        if summary is not None:
            try:
                _validate_data(summary.response_data)
                valid = True
            except (CollectionError, ValueError):
                pass
        complete = [item for item in detail[key] if item["scoreGroups"] == 6 and item["state"] == "complete"]
        rows.append({"period": label(key), "national": {"exists": summary is not None,
            "valid34x6": valid, "capturedAt": aware(summary.captured_at).isoformat() if summary else None,
            "stale": bool(summary and key in current and aware(summary.captured_at) < now - timedelta(hours=2)),
            "priorAvailable": previous(key) in national},
            "provinceDetails": len(detail[key]), "provinceDetailsSixGroups": len(complete),
            "staleDetails": sum(item["stale"] for item in detail[key]),
            "withPriorDetails": sum(item["priorAvailable"] for item in complete),
            "missingProvinces": sorted(set(names.values()) - {item["province"] for item in complete}),
            "details": sorted(detail[key], key=lambda item: item["province"])})
    return {"auditedAt": now.isoformat(), "readOnly": True, "scope": "all", "catalogProvinces": len(names),
            "nationalPeriods": len(national), "detailProvincePeriods": len(snapshots), "periods": rows}


def main():
    if (ROOT / ".env").exists():
        load_environment_file(ROOT / ".env")
    engine = create_database_engine(Settings.from_env())
    try:
        if engine.dialect.name != "postgresql":
            raise RuntimeError("This office audit requires PostgreSQL read-only transaction enforcement")
        with engine.connect().execution_options(isolation_level="REPEATABLE READ") as connection:
            with connection.begin():
                connection.execute(text("SET TRANSACTION READ ONLY"))
                with Session(bind=connection, autoflush=False) as db:
                    report = inventory(db, datetime.now(timezone.utc))
        print(json.dumps(report, ensure_ascii=True, separators=(",", ":")))
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
