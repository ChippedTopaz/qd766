"""Apply the approved additive wallet schema; never activate Credit or services."""
import argparse
import os
import sys
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import create_engine, text

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from qd766.backend.public_deployment import public_settings, read_config
from qd766.backend.database import create_session_factory
from qd766.backend.wallet_runtime import verify_real_wallet_schema
from rehearse_credit_restore import verified_backup
from audit_credit_transition import inventory

TARGET = "20261004_0015"


def require_safe_inventory(report):
    for key in ("legacyAvailable", "legacyReserved", "pendingRequests", "ledgerMismatchAccounts",
                "pendingReserveMismatchAccounts", "orphanLedgerAccounts", "orphanPendingAccounts"):
        if report[key] != 0:
            raise ValueError("Unreviewed legacy Credit or pending requests")
    if report["migrationVersions"] not in (["20261003_0010"], [TARGET]):
        raise ValueError("Unexpected migration baseline")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backup", type=Path, required=True)
    parser.add_argument("--sha256", required=True)
    parser.add_argument("--confirm", action="store_true", help="Apply the approved schema migration")
    args = parser.parse_args()
    engine = None
    phase = "validation"
    try:
        verified_backup(args.backup, args.sha256)
        settings = public_settings(read_config(ROOT / ".env"), read_config(ROOT / ".env.public"),
                                   real_wallet=True, requests_paused=True)
        from sqlalchemy.engine import make_url
        url = make_url(settings.database_url)
        if url.database != "qd766":
            raise ValueError("Approved production database must be qd766")
        engine = create_engine(url, connect_args={"connect_timeout": 5, "options": "-c search_path=public"})
        with engine.connect() as db:
            db.execute(text("SET TRANSACTION READ ONLY"))
            db.execute(text("SET LOCAL statement_timeout='15s'"))
            if db.scalar(text("SELECT current_database()")) != "qd766":
                raise ValueError("Database identity differs")
            report = inventory(db)
            require_safe_inventory(report)
        print("WALLET_MIGRATION_PREFLIGHT=PASS BACKUP_SHA256=PASS DATABASE=qd766", flush=True)
        if not args.confirm:
            print("READ_ONLY; add --confirm to apply the approved additive schema")
            return 0
        phase = "migration"
        from alembic import command
        from alembic.config import Config
        config = Config(str(ROOT / "alembic.ini"))
        config.set_main_option("script_location", str(ROOT / "alembic"))
        # env.py reads Settings.from_env. Override only within this invocation,
        # never let inherited test DB configuration select a different target.
        with patch.dict(os.environ, {"QD766_DATABASE_URL": settings.database_url,
                                     "PGOPTIONS": "-c search_path=public"}):
            command.upgrade(config, TARGET)
        phase = "verification"
        verify_real_wallet_schema(create_session_factory(engine))
        print("WALLET_SCHEMA_READY=" + TARGET)
        print("NO_CREDIT_GRANTED NO_TASK_CHANGED NO_WORKER_STARTED NO_NETLIFY_DEPLOY")
        return 0
    except Exception as error:
        print(f"WALLET_MIGRATION=FAILED PHASE={phase} TYPE={type(error).__name__}; inspect before retry")
        return 1
    finally:
        if engine is not None:
            engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
