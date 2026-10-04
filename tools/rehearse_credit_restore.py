"""Restore into an explicitly named empty test DB, then rehearse wallet migrations.

Never creates/drops a database, changes source DB, or starts a web/collection service.
Retains the restored DB (including private account/session data) for inspection.
"""
import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import URL, make_url

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from qd766.backend.public_deployment import read_config
from qd766.backend.database import create_session_factory
from qd766.backend.wallet_runtime import verify_real_wallet_schema

TARGET_REVISION = "20261004_0015"


def restore_url(config, name):
    if not re.fullmatch(r"qd766_restore_\d{8}_\d{6}", name):
        raise ValueError("Only timestamped restore database names allowed")
    source = make_url(config["QD766_DATABASE_URL"]) if config.get("QD766_DATABASE_URL") else URL.create(
        "postgresql+psycopg", username=config.get("QD766_DATABASE_USER", "qd766_app"),
        password=config.get("QD766_DATABASE_PASSWORD"), host=config.get("QD766_DATABASE_HOST", "127.0.0.1"),
        port=int(config.get("QD766_DATABASE_PORT", "5432")), database=config.get("QD766_DATABASE_NAME", "qd766"))
    if (source.drivername != "postgresql+psycopg" or source.host not in {"127.0.0.1", "localhost", "::1"}
            or source.query or name == source.database or not source.username):
        raise ValueError("Unsafe restore target configuration")
    return source.set(database=name)


def verified_backup(path, expected):
    path = path.resolve(strict=True)
    if path.suffix != ".dump" or not path.is_file() or not path.stat().st_size:
        raise ValueError("Backup must be a nonempty custom dump")
    if not re.fullmatch(r"[0-9a-fA-F]{64}", expected):
        raise ValueError("Expected SHA256 is required")
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    if digest.hexdigest() != expected.lower():
        raise ValueError("Backup checksum mismatch")
    return path


def require_empty_database(engine, name):
    with engine.connect() as db:
        db.execute(text("SET TRANSACTION READ ONLY"))
        identity = db.execute(text("SELECT current_database(), pg_get_userbyid(datdba) = current_user "
                                   "FROM pg_database WHERE datname = current_database()")).one()
        if identity[0] != name or not identity[1]:
            raise ValueError("Test database must be owned by the configured application role")
        objects = db.scalar(text("SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace "
                                 "WHERE n.nspname NOT LIKE 'pg_%' AND n.nspname != 'information_schema'"))
        schemas = db.scalar(text("SELECT count(*) FROM pg_namespace WHERE nspname NOT LIKE 'pg_%' "
                                 "AND nspname NOT IN ('public','information_schema')"))
        if objects or schemas:
            raise ValueError("Restore target is not empty; no overwrite allowed")


def fingerprint(engine):
    """Stable row-level inventory without printing personal data or tokens."""
    with engine.connect().execution_options(isolation_level="REPEATABLE READ") as db:
        db.execute(text("SET TRANSACTION READ ONLY"))
        db.execute(text("SET LOCAL TIME ZONE 'UTC'"))
        db.execute(text("SET LOCAL statement_timeout = '60s'"))
        result = {}
        for name in sorted(inspect(db).get_table_names(schema="public")):
            quoted = db.dialect.identifier_preparer.quote_identifier(name)
            count, digest = db.execute(text(
                f"SELECT count(*), md5(COALESCE(string_agg(md5(row_to_json(t)::text), '' "
                f"ORDER BY md5(row_to_json(t)::text)), '')) FROM public.{quoted} t")).one()
            result[name] = {"rows": count, "digest": digest}
        return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backup", type=Path, required=True)
    parser.add_argument("--sha256", required=True)
    parser.add_argument("--database", required=True)
    parser.add_argument("--connection-file", type=Path, required=True)
    parser.add_argument("--pg-restore", type=Path, default=Path("G:/PostgreSQL/17/bin/pg_restore.exe"))
    args = parser.parse_args()
    engine = None
    phase = "validation"
    try:
        backup = verified_backup(args.backup, args.sha256)
        url = restore_url(read_config(args.connection_file), args.database)
        executable = args.pg_restore.resolve(strict=True)
        engine = create_engine(url, connect_args={"connect_timeout": 5, "options": "-c search_path=public"})
        phase = "empty-target-check"
        require_empty_database(engine, args.database)
        print(f"RESTORE_TARGET={args.database} BACKUP_SHA256=PASS", flush=True)
        phase = "restore"
        environment = dict(os.environ, PGPASSWORD=url.password or "", PGOPTIONS="-c search_path=public")
        command = [str(executable), "--no-password", "--no-owner", "--no-privileges",
                   "--single-transaction", "--exit-on-error", "--schema=public",
                   "--host=" + url.host, "--port=" + str(url.port or 5432),
                   "--username=" + url.username, "--dbname=" + args.database, str(backup)]
        restored = subprocess.run(command, env=environment, capture_output=True, timeout=180)
        if restored.returncode:
            raise RuntimeError("Restore rejected; database retained without automatic cleanup")
        before = fingerprint(engine)
        if "user_accounts" not in before or "alembic_version" not in before:
            raise ValueError("Restored application schema missing")
        with engine.connect() as db:
            revisions = list(db.execute(text("SELECT version_num FROM public.alembic_version")).scalars())
        if revisions != ["20261003_0010"]:
            raise ValueError("Backup revision differs from reviewed baseline")
        print("BACKUP_RESTORE=PASS BASELINE=20261003_0010", flush=True)
        phase = "migration"
        from alembic import command as alembic_command
        from alembic.config import Config
        config = Config(str(ROOT / "alembic.ini"))
        config.set_main_option("script_location", str(ROOT / "alembic"))
        # env.py uses Settings.from_env: override URL in this process only.
        with patch.dict(os.environ, {"QD766_DATABASE_URL": url.render_as_string(hide_password=False)}):
            alembic_command.upgrade(config, TARGET_REVISION)
        after = fingerprint(engine)
        if any(after.get(name) != value for name, value in before.items() if name != "alembic_version"):
            raise ValueError("Existing table rows changed during migrations")
        new_tables = set(after) - set(before)
        if any(after[name]["rows"] != 0 for name in new_tables):
            raise ValueError("Unexpected seeded data during migrations")
        verify_real_wallet_schema(create_session_factory(engine))
        from audit_credit_transition import inventory
        with engine.connect() as db:
            db.execute(text("SET TRANSACTION READ ONLY"))
            report = inventory(db)
        print(json.dumps({"restoreDatabase": args.database, "migration": TARGET_REVISION,
            "preservedTables": len(before) - 1, "newEmptyTables": sorted(new_tables),
            "accountCount": report["accounts"], "legacyAvailable": report["legacyAvailable"],
            "legacyReserved": report["legacyReserved"], "ledgerMismatchAccounts": report["ledgerMismatchAccounts"],
            "pendingReserveMismatchAccounts": report["pendingReserveMismatchAccounts"],
            "realWalletSchema": "PASS", "productionChanged": False}, indent=2))
        print("RESTORE_REHEARSAL=PASS DB_RETAINED NO_SERVICE_STARTED NO_CRAWLING")
        return 0
    except Exception as error:
        print(f"RESTORE_REHEARSAL=FAILED PHASE={phase} TYPE={type(error).__name__}; "
              "no production fallback or automatic database deletion")
        return 1
    finally:
        if engine is not None:
            engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
