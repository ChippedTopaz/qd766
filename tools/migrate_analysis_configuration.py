"""Add configuration tables only; explicit confirmation and verified fresh backup."""
import argparse,hashlib,sys
from pathlib import Path
from datetime import datetime,timezone,timedelta
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from alembic import command
from alembic.config import Config
from sqlalchemy import text,inspect
from qd766.backend.config import Settings,load_environment_file
from qd766.backend.database import create_database_engine
from qd766.backend.models import AnalysisConfigHead,AnalysisConfigRevision

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--backup',type=Path);parser.add_argument('--confirm',action='store_true');args=parser.parse_args()
    if not args.confirm:print('PLAN_ONLY_NO_DATABASE_CONNECTION');return
    if not args.backup:raise SystemExit('FRESH_BACKUP_REQUIRED')
    path=args.backup.resolve(strict=True);checksum=Path(str(path)+'.sha256')
    age=datetime.now(timezone.utc)-datetime.fromtimestamp(path.stat().st_mtime,timezone.utc)
    if path.suffix!='.dump' or not path.stat().st_size or not checksum.is_file() or not timedelta(0)<=age<timedelta(hours=24):raise SystemExit('FRESH_VERIFIED_BACKUP_REQUIRED')
    with path.open('rb') as stream:digest=hashlib.file_digest(stream,'sha256').hexdigest()
    if digest!=checksum.read_text(encoding='ascii').split()[0].lower():raise SystemExit('BACKUP_CHECKSUM_FAILED')
    load_environment_file(ROOT/'.env');engine=create_database_engine(Settings.from_env())
    try:
        with engine.connect() as connection:
            if engine.dialect.name!='postgresql':raise SystemExit('OFFICE_POSTGRESQL_REQUIRED')
            connection.execute(text('SET TRANSACTION READ ONLY'))
            versions=list(connection.execute(text('SELECT version_num FROM public.alembic_version')).scalars())
            if versions not in [['20261007_0019'],['20261007_0020']]:raise SystemExit('REVIEWED_QUEUE_SCHEMA_REQUIRED')
        config=Config(str(ROOT/'alembic.ini'));config.set_main_option('script_location',str(ROOT/'alembic'))
        command.upgrade(config,'20261007_0020')
        inspector=inspect(engine)
        for model in (AnalysisConfigHead,AnalysisConfigRevision):
            if not set(model.__table__.columns.keys())<={c['name'] for c in inspector.get_columns(model.__tablename__,schema='public')}:
                raise SystemExit('CONFIGURATION_SCHEMA_INCOMPLETE')
        print('ANALYSIS_CONFIGURATION_SCHEMA_READY_NO_RESTART_NO_CONFIG_CHANGE')
    finally:engine.dispose()

if __name__=='__main__':main()
