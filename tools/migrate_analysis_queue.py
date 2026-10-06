"""Explicit, drained-queue migration. Never activates or restarts services."""
import argparse,hashlib,sys
from pathlib import Path
from datetime import datetime,timezone,timedelta
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from alembic import command
from alembic.config import Config
from qd766.backend.config import Settings,load_environment_file
from qd766.backend.database import create_database_engine
from sqlalchemy import text
from qd766.backend.analysis_queue import verify_schema

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--backup',type=Path)
    parser.add_argument('--confirm',action='store_true')
    parser.add_argument('--requests-paused',action='store_true',help='Operator confirms admission paused and in-flight requests drained')
    args=parser.parse_args()
    if not args.confirm:print('PLAN_ONLY_NO_DATABASE_CONNECTION');return
    if not args.requests_paused or not args.backup:raise SystemExit('PAUSE_AND_FRESH_BACKUP_REQUIRED')
    path=args.backup.resolve(strict=True);checksum=Path(str(path)+'.sha256')
    age=datetime.now(timezone.utc)-datetime.fromtimestamp(path.stat().st_mtime,timezone.utc)
    if path.suffix!='.dump' or not path.stat().st_size or not checksum.is_file() or not timedelta(0)<=age<timedelta(hours=24):
        raise SystemExit('FRESH_VERIFIED_BACKUP_REQUIRED')
    with path.open('rb') as stream:digest=hashlib.file_digest(stream,'sha256').hexdigest()
    if digest!=checksum.read_text(encoding='ascii').split()[0].lower():raise SystemExit('BACKUP_CHECKSUM_FAILED')
    load_environment_file(ROOT/'.env');engine=create_database_engine(Settings.from_env())
    try:
        with engine.connect() as connection:
            if engine.dialect.name!='postgresql':raise SystemExit('OFFICE_POSTGRESQL_REQUIRED')
            connection.execute(text('SET TRANSACTION READ ONLY'))
            versions=list(connection.execute(text('SELECT version_num FROM public.alembic_version')).scalars())
            if versions not in [['20261006_0018'],['20261007_0019']]:raise SystemExit('REVIEWED_ANALYSIS_SCHEMA_REQUIRED')
            if connection.scalar(text("SELECT count(*) FROM public.gemini_analyses WHERE state IN ('queued','running')")):
                raise SystemExit('PENDING_ANALYSES_MUST_FINISH_OR_BE_RECONCILED_FIRST')
        config=Config(str(ROOT/'alembic.ini'));config.set_main_option('script_location',str(ROOT/'alembic'))
        command.upgrade(config,'20261007_0019');verify_schema(engine)
        print('ANALYSIS_QUEUE_SCHEMA_READY_NO_FEATURE_ACTIVATION')
    finally:engine.dispose()

if __name__=='__main__':main()
