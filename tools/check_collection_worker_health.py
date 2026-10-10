"""Read-only queue health, no account data, no upstream call, no wallet mutation."""
import sys, json
from pathlib import Path
from datetime import datetime, timezone
from sqlalchemy import text
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from qd766.backend.config import Settings, load_environment_file
from qd766.backend.database import create_database_engine


def main():
    load_environment_file(ROOT/'.env')
    engine = create_database_engine(Settings.from_env())
    try:
        with engine.connect() as db:
            db.execute(text('SET TRANSACTION READ ONLY'))
            counts = dict(db.execute(text('SELECT state,count(*) FROM collection_jobs GROUP BY state')).all())
            oldest = db.scalar(text("SELECT min(created_at) FROM collection_jobs WHERE state='queued'"))
            last_success = db.scalar(text("SELECT max(updated_at) FROM collection_jobs WHERE state='succeeded'"))
            control = db.execute(text("SELECT circuit_state,lease_locked_at FROM collection_controls WHERE key='dvcqg'")).mappings().first()
        now = datetime.now(timezone.utc)
        age = lambda value: max(0,(now-value).total_seconds()) if value else None
        queue_age, lease_age, success_age = age(oldest), age(control['lease_locked_at']) if control else None, age(last_success)
        if not control:
            status = 'CONTROL_MISSING'
        elif control['circuit_state']=='open':
            status = 'SAFETY_PAUSED'
        elif lease_age is not None and lease_age >= 1800:
            status = 'LEASE_STALE'
        elif counts.get('queued',0) and queue_age >= 600 and lease_age is None and (success_age is None or success_age >= 600):
            status = 'QUEUE_STALLED'
        else:
            status = 'PROCESSING' if counts.get('running',0) else 'WAITING' if counts.get('queued',0) else 'IDLE'
        print(json.dumps({'status':status,'checkedAt':now.isoformat(),'queued':counts.get('queued',0),
            'running':counts.get('running',0),'oldestQueuedSeconds':queue_age,
            'lastSuccessAgeSeconds':success_age,'leaseAgeSeconds':lease_age},ensure_ascii=False))
        return 2 if status in {'QUEUE_STALLED','LEASE_STALE','CONTROL_MISSING'} else 0
    finally:
        engine.dispose()

if __name__=='__main__':
    raise SystemExit(main())
