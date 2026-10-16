"""Apply only the approved additive notices revision after a fresh verified backup."""
import argparse
import hashlib
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from alembic import command
from alembic.config import Config
from sqlalchemy import inspect,text
from qd766.backend.config import Settings,load_environment_file
from qd766.backend.database import create_database_engine
from qd766.backend.models import SystemNotice,SystemNoticeDismissal

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--backup',type=Path,required=True)
    parser.add_argument('--confirm',action='store_true')
    args=parser.parse_args()
    if not args.confirm:
        print('PLAN_ONLY_NO_DATABASE_CONNECTION');return
    path=args.backup.resolve(strict=True)
    age=datetime.now(timezone.utc)-datetime.fromtimestamp(path.stat().st_mtime,timezone.utc)
    if path.suffix!='.dump' or not path.stat().st_size or not timedelta(0)<=age<timedelta(hours=24):
        raise SystemExit('FRESH_BACKUP_REQUIRED')
    expected=Path(str(path)+'.sha256').read_text(encoding='ascii').split()[0].lower()
    with path.open('rb') as stream:
        if hashlib.file_digest(stream,'sha256').hexdigest()!=expected:
            raise SystemExit('BACKUP_CHECKSUM_FAILED')
    load_environment_file(ROOT/'.env')
    engine=create_database_engine(Settings.from_env())
    try:
        if engine.dialect.name!='postgresql':raise SystemExit('POSTGRESQL_REQUIRED')
        with engine.connect() as db:
            versions=list(db.execute(text('SELECT version_num FROM alembic_version')).scalars())
            if versions not in [['20261014_0028'],['20261016_0029']]:
                raise SystemExit('REVIEWED_SCHEMA_REQUIRED')
        config=Config(str(ROOT/'alembic.ini'))
        config.set_main_option('script_location',str(ROOT/'alembic'))
        command.upgrade(config,'20261016_0029')
        for model in (SystemNotice,SystemNoticeDismissal):
            actual={c['name'] for c in inspect(engine).get_columns(model.__tablename__)}
            if actual!=set(model.__table__.columns.keys()):raise SystemExit('NOTICE_SCHEMA_MISMATCH')
        print('SYSTEM_NOTICES_SCHEMA=PASS 20261016_0029; no content published')
    finally:engine.dispose()

if __name__=='__main__':main()
