"""Apply only schema 0025 after a verified fresh backup. Never seed formulas."""
import argparse
import hashlib
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from alembic import command
from alembic.config import Config
from sqlalchemy import text
from qd766.backend.config import Settings, load_environment_file
from qd766.backend.database import create_database_engine


def formula_digest(engine):
    with engine.connect() as db:
        db.execute(text('SET TRANSACTION READ ONLY'))
        rows = db.execute(text('SELECT version, content FROM formula_config_revisions ORDER BY version')).all()
        heads = db.execute(text('SELECT id, version FROM formula_config_head ORDER BY id')).all()
        payload = {'revisions': [list(row) for row in rows], 'heads': [list(row) for row in heads]}
        return hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--backup', type=Path, required=True)
    parser.add_argument('--confirm', action='store_true')
    args = parser.parse_args()
    if not args.confirm:
        print('PLAN_ONLY TARGET=20261009_0025 NO_DATABASE_CONNECTION')
        return
    backup = args.backup.absolute()
    checksum = Path(str(backup) + '.sha256')
    age = datetime.now(timezone.utc) - datetime.fromtimestamp(backup.stat().st_mtime, timezone.utc)
    if backup.suffix != '.dump' or backup.stat().st_size == 0 or not checksum.is_file() or not timedelta(0) <= age < timedelta(hours=24):
        raise SystemExit('FRESH_VERIFIED_BACKUP_REQUIRED')
    with backup.open('rb') as stream:
        digest = hashlib.file_digest(stream, 'sha256').hexdigest()
    if digest != checksum.read_text(encoding='ascii').split()[0].lower():
        raise SystemExit('BACKUP_CHECKSUM_FAILED')
    load_environment_file(ROOT / '.env')
    engine = create_database_engine(Settings.from_env())
    try:
        if engine.dialect.name != 'postgresql':
            raise SystemExit('POSTGRESQL_REQUIRED')
        with engine.connect() as db:
            db.execute(text('SET TRANSACTION READ ONLY'))
            versions = list(db.execute(text('SELECT version_num FROM alembic_version')).scalars())
            if versions not in [['20261008_0024'], ['20261009_0025']]:
                raise SystemExit('REVIEWED_SCHEMA_0024_OR_0025_REQUIRED')
        before = formula_digest(engine)
        config = Config(str(ROOT / 'alembic.ini'))
        config.set_main_option('script_location', str(ROOT / 'alembic'))
        command.upgrade(config, '20261009_0025')
        if formula_digest(engine) != before:
            raise SystemExit('FORMULA_CONFIGURATION_CHANGED_REVIEW_REQUIRED')
        print('REGISTRATION_SCHEMA=20261009_0025 SAVED_FORMULAS_PRESERVED=PASS')
        print('NO_RESEED NO_CREDIT_CHANGE NO_DATASET_CHANGE NO_TASK_CHANGE')
    finally:
        engine.dispose()


if __name__ == '__main__':
    main()
