"""SELECT-only production preflight and local raw-profile check. No provider calls."""
import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from sqlalchemy import select, text

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from qd766.backend.config import Settings, load_environment_file
from qd766.backend.database import create_database_engine, create_session_factory
from qd766.backend.models import DailyObservation
from qd766.backend.source_monitor import capture_profiles, closed_month_baselines


def main():
    parser = argparse.ArgumentParser(); parser.add_argument('--check', action='store_true')
    if not parser.parse_args().check:
        print('PLAN_ONLY NO_DATABASE_CONNECTION NO_PROVIDER_REQUEST'); return 0
    load_environment_file(ROOT / '.env'); engine = create_database_engine(Settings.from_env())
    try:
        started = time.perf_counter()
        with create_session_factory(engine)() as db:
            db.execute(text('SET TRANSACTION READ ONLY'))
            db.execute(text("SET LOCAL statement_timeout='15s'"))
            revision = db.scalar(text('SELECT version_num FROM public.alembic_version'))
            if revision not in ('20261011_0027', '20261014_0028'): raise ValueError('Unexpected schema')
            periods = closed_month_baselines(db, datetime.now(timezone.utc))
            latest = db.scalar(select(DailyObservation).order_by(DailyObservation.report_date.desc()).limit(1))
            if latest is None: raise ValueError('No published daily baseline')
            observations = list(db.scalars(select(DailyObservation).where(DailyObservation.report_date == latest.report_date)))
            profiles = 0; absent = 0
            for row in observations:
                folder = ROOT / 'data/daily-collection' / str(row.report_date) / 'captures' / f'{row.period_type}-{row.year}-{row.period_value or 0}' / str(row.root_department_id)
                if not (folder / 'manifest.json').is_file(): absent += 1; continue
                manifest = json.loads((folder / 'manifest.json').read_text(encoding='utf-8'))
                profiles += len(capture_profiles(folder, manifest))
            print(json.dumps({'check': 'PASS SELECT-ONLY', 'schema': revision,
                'closedMonthlySamplesPerDay': len(periods), 'expectedSourceRequests': len(periods),
                'reportDate': str(latest.report_date), 'publishedDailyBlocks': len(observations),
                'localRawProfilesValidated': profiles, 'missingLocalRawBlocks': absent,
                'elapsedMs': round((time.perf_counter() - started) * 1000, 2),
                'providerRequestsMade': 0, 'publishedWrites': 0, 'creditWrites': 0}, ensure_ascii=False))
        return 0
    except Exception as error:
        print('SOURCE_MONITOR_CHECK=FAILED TYPE=' + type(error).__name__); return 1
    finally: engine.dispose()


if __name__ == '__main__': raise SystemExit(main())
