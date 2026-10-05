#!/usr/bin/env python3
"""Append versioned all-scope province batches; never change Credit or circuit."""
from __future__ import annotations
import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from sqlalchemy import select

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from qd766.periods import PeriodSelection
from qd766.backend.config import Settings, load_environment_file
from qd766.backend.database import create_database_engine, create_session_factory
from qd766.backend.models import CollectionControl, ProvinceCollectionBatch
from qd766.backend.province_batches import create_province_batch
from qd766.province_roots import load_province_roots
from manage_province_batch import _catalog_version, _payload

def refresh_periods(year: int, now: datetime) -> list[PeriodSelection]:
    if year < 2000 or year > now.year:
        raise ValueError('Year must be available and not in the future')
    months = now.month if year == now.year else 12
    quarters = (now.month - 1) // 3 + 1 if year == now.year else 4
    # Most recent closed month first, then remaining months and quarters/year.
    values = list(range(months, 0, -1))
    if year == now.year and months > 1:
        values.remove(months - 1)
        values.insert(0, months - 1)
    return ([PeriodSelection('month', year, value) for value in values]
            + [PeriodSelection('quarter', year, value) for value in range(quarters, 0, -1)]
            + [PeriodSelection('year', year)])

def main() -> int:
    sys.stdout.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser()
    parser.add_argument('--year', type=int, required=True)
    parser.add_argument('--refresh-key', required=True, help='Reuse this key to avoid duplicate batches')
    parser.add_argument('--confirm', action='store_true', help='Without this flag only print the plan')
    args = parser.parse_args()
    if not args.refresh_key.strip() or len(args.refresh_key) > 120:
        parser.error('refresh-key must contain 1..120 characters')
    periods = refresh_periods(args.year, datetime.now().astimezone())
    roots = list(load_province_roots().values())
    if len(roots) != 34:
        raise RuntimeError('Expected validated 34-province catalog')
    if not args.confirm:
        print(json.dumps({'state':'planned', 'periods': [[p.type,p.year,p.value] for p in periods],
            'provincePeriods':len(periods)*len(roots), 'minimumDetailCalls':len(periods)*len(roots)*6}))
        return 0
    load_environment_file(ROOT / '.env')
    engine = create_database_engine(Settings.from_env())
    factory = create_session_factory(engine)
    try:
        with factory.begin() as session:
            control = session.scalar(select(CollectionControl).where(CollectionControl.key == 'dvcqg').with_for_update())
            if control is None or control.circuit_state != 'closed':
                raise RuntimeError('Collection control missing or circuit open; nothing queued')
            active = list(session.scalars(select(ProvinceCollectionBatch).where(
                ProvinceCollectionBatch.state.in_(['queued','running','failed','halted']))))
            # Rerunning an identical cycle is safe, but do not add overlapping work.
            if active:
                raise RuntimeError('Existing province batches require completion/review; nothing queued')
            outputs = []
            for period in periods:
                batch, created = create_province_batch(session, roots, period,
                    catalog_version=_catalog_version(), refresh_key=args.refresh_key)
                outputs.append(_payload(session,batch,created=created))
        print(json.dumps({'state':'queued','refreshKey':args.refresh_key,
            'preservesOldSnapshots':True,'scope':'all','batches':outputs},ensure_ascii=False,indent=2))
        return 0
    finally:
        engine.dispose()

if __name__ == '__main__':
    raise SystemExit(main())
