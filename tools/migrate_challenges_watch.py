"""Reviewed additive 0026/0027 migration, after verified backup; never reseed."""
import argparse
import hashlib
import sys
from datetime import datetime,timedelta,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from alembic import command
from alembic.config import Config
from sqlalchemy import text
from qd766.backend.config import Settings,load_environment_file
from qd766.backend.database import create_database_engine
from qd766.backend.wallet_runtime import verify_real_wallet_schema
from sqlalchemy.orm import sessionmaker
from migrate_public_registration import formula_digest

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--backup',type=Path,required=True)
    parser.add_argument('--confirm',action='store_true')
    args=parser.parse_args()
    if not args.confirm:
        print('PLAN_ONLY TARGET=20261011_0027 NO_DATABASE_CONNECTION');return
    backup=args.backup.resolve();checksum=Path(str(backup)+'.sha256')
    age=datetime.now(timezone.utc)-datetime.fromtimestamp(backup.stat().st_mtime,timezone.utc)
    if backup.suffix!='.dump' or backup.stat().st_size==0 or not checksum.is_file() or not timedelta(0)<=age<timedelta(hours=24):
        raise SystemExit('FRESH_VERIFIED_BACKUP_REQUIRED')
    with backup.open('rb') as stream:digest=hashlib.file_digest(stream,'sha256').hexdigest()
    if digest!=checksum.read_text(encoding='ascii').split()[0].lower():raise SystemExit('BACKUP_CHECKSUM_FAILED')
    load_environment_file(ROOT/'.env');engine=create_database_engine(Settings.from_env())
    try:
        if engine.dialect.name!='postgresql':raise SystemExit('POSTGRESQL_REQUIRED')
        with engine.connect() as db:
            db.execute(text('SET TRANSACTION READ ONLY'))
            revisions=list(db.execute(text('SELECT version_num FROM alembic_version')).scalars())
            if revisions not in [['20261009_0025'],['20261011_0026'],['20261011_0027']]:raise SystemExit('REVIEWED_SCHEMA_REQUIRED')
        before=formula_digest(engine)
        config=Config(str(ROOT/'alembic.ini'));config.set_main_option('script_location',str(ROOT/'alembic'))
        command.upgrade(config,'20261011_0027')
        if formula_digest(engine)!=before:raise SystemExit('FORMULA_CONFIGURATION_CHANGED_REVIEW_REQUIRED')
        verify_real_wallet_schema(sessionmaker(bind=engine),shared_registration=True)
        print('CHALLENGE_WATCH_SCHEMA=20261011_0027 SAVED_FORMULAS_PRESERVED=PASS WALLET_SCHEMA=PASS')
        print('NO_RESEED NO_CREDIT_CHANGE NO_DATASET_CHANGE NO_TASK_CHANGE')
    finally:engine.dispose()

if __name__=='__main__':main()
