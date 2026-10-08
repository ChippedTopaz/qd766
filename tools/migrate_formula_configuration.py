"""Explicitly authorized deployment import; no HTTP authentication bypass.

Requires a verified fresh database backup and a pinned saved-preview digest.
Only the initial seed may be replaced by a NEW audited immutable revision.
"""
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
from sqlalchemy import select, text
from sqlalchemy.orm import Session
from qd766.backend.admin import audit
from qd766.backend.analysis_configuration import save_lock
from qd766.backend.config import Settings, load_environment_file
from qd766.backend.database import create_database_engine
from qd766.backend.formula_configuration import SEED, validate_content
from qd766.backend.models import FormulaConfigHead, FormulaConfigRevision, UserAccount


def import_saved(db, content, digest):
    validate_content(content)
    with save_lock(db):
        head = db.get(FormulaConfigHead, 1)
        row = db.get(FormulaConfigRevision, head.version) if head else None
        if row and row.content == content:
            return row.version
        if not row or head.version != 1 or row.content != SEED:
            raise RuntimeError('EXISTING_PRODUCTION_EDITS_PRESERVED_IMPORT_STOPPED')
        admins = list(db.scalars(select(UserAccount).where(
            UserAccount.role == 'admin', UserAccount.active.is_(True),
            UserAccount.trial_admitted.is_(True))))
        if len(admins) != 1:
            raise RuntimeError('UNAMBIGUOUS_ACTIVE_ADMIN_REQUIRED')
        actor = admins[0]
        db.add(FormulaConfigRevision(version=2, content=content,
            note='Nhập nội dung đã lưu ở bản thử nghiệm theo yêu cầu quản trị khi deploy.',
            actor_id=actor.id, created_at=datetime.now(timezone.utc)))
        db.flush()
        head.version = 2
        audit(db, actor, 'formula_configuration_saved', version=2,
              source='authorized_deployment_import', snapshot_sha256=digest)
        return 2


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--backup', type=Path)
    parser.add_argument('--snapshot', type=Path)
    parser.add_argument('--snapshot-sha256')
    parser.add_argument('--confirm', action='store_true')
    args = parser.parse_args()
    if not args.confirm:
        print('PLAN_ONLY_NO_DATABASE_CONNECTION TARGET=20261008_0024')
        return
    if not args.backup or not args.snapshot or not args.snapshot_sha256:
        raise SystemExit('VERIFIED_BACKUP_AND_PINNED_SAVED_SNAPSHOT_REQUIRED')
    backup = args.backup.resolve(strict=True)
    checksum = Path(str(backup) + '.sha256')
    age = datetime.now(timezone.utc) - datetime.fromtimestamp(backup.stat().st_mtime, timezone.utc)
    if backup.suffix != '.dump' or not backup.stat().st_size or not checksum.is_file() or not timedelta(0) <= age < timedelta(hours=24):
        raise SystemExit('FRESH_VERIFIED_BACKUP_REQUIRED')
    with backup.open('rb') as stream:
        digest = hashlib.file_digest(stream, 'sha256').hexdigest()
    if digest != checksum.read_text(encoding='ascii').split()[0].lower():
        raise SystemExit('BACKUP_CHECKSUM_FAILED')
    raw = args.snapshot.resolve(strict=True).read_bytes()
    snapshot_digest = hashlib.sha256(raw).hexdigest()
    if snapshot_digest != args.snapshot_sha256.lower():
        raise SystemExit('SAVED_SNAPSHOT_CHANGED_IMPORT_STOPPED')
    content = json.loads(raw)['configuration']
    validate_content(content)
    load_environment_file(ROOT / '.env')
    engine = create_database_engine(Settings.from_env())
    try:
        with engine.connect() as connection:
            if engine.dialect.name != 'postgresql':
                raise SystemExit('OFFICE_POSTGRESQL_REQUIRED')
            connection.execute(text('SET TRANSACTION READ ONLY'))
            versions = list(connection.execute(text('SELECT version_num FROM public.alembic_version')).scalars())
            if versions not in [['20261007_0023'], ['20261008_0024']]:
                raise SystemExit('REVIEWED_SCHEMA_0023_REQUIRED')
            admins = connection.execute(select(UserAccount.id).where(
                UserAccount.role == 'admin', UserAccount.active.is_(True),
                UserAccount.trial_admitted.is_(True))).all()
            if len(admins) != 1:
                raise SystemExit('UNAMBIGUOUS_ACTIVE_ADMIN_REQUIRED')
        config = Config(str(ROOT / 'alembic.ini'))
        config.set_main_option('script_location', str(ROOT / 'alembic'))
        command.upgrade(config, '20261008_0024')
        with Session(engine) as db, db.begin():
            version = import_saved(db, content, snapshot_digest)
        with Session(engine) as db:
            head = db.get(FormulaConfigHead, 1)
            saved = db.get(FormulaConfigRevision, head.version)
            if saved.content != content or head.version != version:
                raise SystemExit('FORMULA_READBACK_MISMATCH')
        print(f'FORMULA_SCHEMA_READY=20261008_0024 FORMULA_VERSION={version}')
        print('SAVED_FORMULA_READBACK=PASS NO_WALLET_CHANGE NO_DATASET_CHANGE NO_RESTART')
    finally:
        engine.dispose()


if __name__ == '__main__':
    main()
