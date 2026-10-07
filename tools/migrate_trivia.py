"""Reviewed additive upgrade 0022 -> 0023; never restart or modify credits."""
import argparse,hashlib,sys
from pathlib import Path
from datetime import datetime,timezone,timedelta
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from alembic import command
from alembic.config import Config
from sqlalchemy import text,inspect
from qd766.backend.config import Settings,load_environment_file
from qd766.backend.database import create_database_engine
from qd766.backend.models import TriviaQuestion,TriviaProfile,TriviaAnswer

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--backup',type=Path);parser.add_argument('--confirm',action='store_true');args=parser.parse_args()
    if not args.confirm:print('PLAN_ONLY_NO_DATABASE_CONNECTION TARGET=20261007_0023');return
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
            if versions not in [['20261007_0022'],['20261007_0023']]:raise SystemExit('REVIEWED_SCHEMA_0022_REQUIRED')
        config=Config(str(ROOT/'alembic.ini'));config.set_main_option('script_location',str(ROOT/'alembic'))
        command.upgrade(config,'20261007_0023')
        for model in (TriviaQuestion,TriviaProfile,TriviaAnswer):
            if not set(model.__table__.columns.keys())<={c['name'] for c in inspect(engine).get_columns(model.__tablename__,schema='public')}:
                raise SystemExit('TRIVIA_SCHEMA_INCOMPLETE')
        print('TRIVIA_SCHEMA_READY NO_RESTART NO_CREDIT_CHANGE NO_QUESTION_PUBLISHED')
    finally:engine.dispose()

if __name__=='__main__':main()
