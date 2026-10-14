"""Pinned additive 0028 only, with fresh verified backup; never publish samples."""
import argparse
import hashlib
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from alembic import command
from alembic.config import Config
from sqlalchemy import inspect, text
from qd766.backend.config import Settings, load_environment_file
from qd766.backend.database import create_database_engine, create_session_factory
from qd766.backend.models import Base
from qd766.backend.source_monitor import TABLES
from qd766.backend.wallet_runtime import verify_real_wallet_schema
from migrate_public_registration import formula_digest

TARGET = '20261014_0028'


def verify_backup(path):
    # Backup is read-only. pg_dump's protected Windows ACL can allow reading
    # while denying GetFinalPathNameByHandle used by Path.resolve().
    path = path.absolute()
    checksum = Path(str(path) + '.sha256')
    age = datetime.now(timezone.utc) - datetime.fromtimestamp(path.stat().st_mtime, timezone.utc)
    if path.suffix != '.dump' or not path.stat().st_size or not checksum.is_file() or not timedelta(0) <= age < timedelta(hours=24):
        raise ValueError('Fresh verified dump required')
    with path.open('rb') as stream:
        digest = hashlib.file_digest(stream, 'sha256').hexdigest()
    if digest != checksum.read_text(encoding='ascii').split()[0].lower():
        raise ValueError('Backup checksum mismatch')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--backup', type=Path)
    parser.add_argument('--confirm', action='store_true')
    args = parser.parse_args()
    if not args.confirm:
        print('PLAN_ONLY TARGET=20261014_0028 NO_DATABASE_CONNECTION'); return 0
    engine = None; phase = 'backup-verification'
    try:
        if not args.backup: raise ValueError('Backup required')
        verify_backup(args.backup)
        phase = 'database-preflight'
        load_environment_file(ROOT / '.env')
        settings = Settings.from_env(); engine = create_database_engine(settings)
        if engine.dialect.name != 'postgresql': raise ValueError('PostgreSQL required')
        with engine.connect() as db:
            db.execute(text('SET TRANSACTION READ ONLY'))
            if db.scalar(text('SELECT current_database()')) != 'qd766': raise ValueError('Unexpected database')
            versions = list(db.execute(text('SELECT version_num FROM public.alembic_version')).scalars())
            if versions not in [['20261011_0027'], [TARGET]]: raise ValueError('Reviewed predecessor required')
        before = formula_digest(engine)
        phase = 'migration'
        config = Config(str(ROOT / 'alembic.ini'))
        config.set_main_option('script_location', str(ROOT / 'alembic'))
        # Bounded lock wait; keep legacy services available rather than waiting indefinitely.
        with patch.dict(os.environ, {'QD766_DATABASE_URL': settings.database_url,
                                     'PGOPTIONS': '-c search_path=public -c lock_timeout=5000 -c statement_timeout=60000'}):
            command.upgrade(config, TARGET)
        inspector = inspect(engine)
        phase = 'post-migration-verification'
        for name in TABLES:
            if not set(Base.metadata.tables[name].columns.keys()) <= {c['name'] for c in inspector.get_columns(name, schema='public')}:
                raise ValueError('Monitor schema incomplete')
        verify_real_wallet_schema(create_session_factory(engine), shared_registration=True)
        if formula_digest(engine) != before: raise ValueError('Saved formula changed; review required')
        print('SOURCE_MONITOR_SCHEMA=20261014_0028 SAVED_FORMULAS_PRESERVED=PASS WALLET_SCHEMA=PASS')
        print('NO_SNAPSHOT_UPDATE NO_CREDIT_CHANGE NO_TASK_CHANGE NO_RESTART NO_DEPLOY')
        return 0
    except Exception as error:
        # Connection errors may contain credentials. Print only the type.
        print('SOURCE_MONITOR_MIGRATION=FAILED PHASE=' + phase + ' TYPE=' + type(error).__name__)
        return 1
    finally:
        if engine is not None: engine.dispose()


if __name__ == '__main__': raise SystemExit(main())
