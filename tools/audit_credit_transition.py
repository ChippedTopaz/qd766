"""Read-only inventory, not a migration or permission to activate wallets."""
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import make_url

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from qd766.backend.config import Settings, load_environment_file


def reconcile(accounts, ledger, requests):
    totals = {}
    for entry in ledger:
        pair = totals.setdefault(str(entry["account_id"]), [0, 0])
        pair[0] += entry["available_delta"]
        pair[1] += entry["reserved_delta"]
    pending = {}
    for request in requests:
        if request["state"] in ("reserved", "waiting"):
            key = str(request["account_id"])
            pending[key] = pending.get(key, 0) + request["credit_cost"]
    known = {str(a["id"]) for a in accounts}
    return {
        "accounts": len(accounts),
        "legacyAvailable": sum(a["credit_balance"] for a in accounts),
        "legacyReserved": sum(a["credit_reserved"] for a in accounts),
        "accountsWithAvailable": sum(a["credit_balance"] > 0 for a in accounts),
        "accountsWithReserved": sum(a["credit_reserved"] > 0 for a in accounts),
        "ledgerMismatchAccounts": sum(
            totals.get(str(a["id"]), [0, 0]) != [a["credit_balance"], a["credit_reserved"]]
            for a in accounts),
        "pendingReserveMismatchAccounts": sum(
            pending.get(str(a["id"]), 0) != a["credit_reserved"] for a in accounts),
        "pendingRequests": sum(r["state"] in ("reserved", "waiting") for r in requests),
        "pendingCredit": sum(pending.values()),
        "orphanLedgerAccounts": len(set(totals) - known),
        "orphanPendingAccounts": len(set(pending) - known),
        "sourceClassification": "UNDETERMINED_ADMIN_REVIEW_REQUIRED",
    }


def inventory(db):
    tables = set(inspect(db).get_table_names(schema="public"))
    required = {"user_accounts", "credit_ledger_entries", "paid_data_requests"}
    if not required <= tables:
        raise ValueError("Required legacy tables missing")
    def rows(query):
        return list(db.execute(text(query)).mappings())
    accounts = rows("SELECT id, credit_balance, credit_reserved FROM public.user_accounts")
    ledger = rows("SELECT account_id, available_delta, reserved_delta FROM public.credit_ledger_entries")
    requests = rows("SELECT account_id, state, credit_cost FROM public.paid_data_requests")
    report = reconcile(accounts, ledger, requests)
    report["capturedAt"] = datetime.now(timezone.utc).isoformat()
    report["migrationVersions"] = [r[0] for r in db.execute(text(
        "SELECT version_num FROM public.alembic_version"))] if "alembic_version" in tables else []
    wallet_tables = ("credit_lots", "credit_holds", "credit_wallet_events",
                     "subscription_cycles", "credit_wallet_enrollments")
    report["walletTables"] = {name: (db.scalar(text(f"SELECT count(*) FROM public.{name}"))
                                      if name in tables else None) for name in wallet_tables}
    report["activationReady"] = False
    report["mode"] = "READ_ONLY_NO_MIGRATION_NO_CREDIT_CHANGES"
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--connection-file", type=Path, required=True)
    args = parser.parse_args()
    engine = None
    try:
        load_environment_file(args.connection_file.resolve(strict=True))
        url = make_url(Settings.from_env().database_url)
        if url.drivername != "postgresql+psycopg" or url.host not in ("127.0.0.1", "localhost", "::1"):
            raise ValueError("Only local PostgreSQL allowed")
        engine = create_engine(url, connect_args={"connect_timeout": 5})
        with engine.connect().execution_options(isolation_level="REPEATABLE READ") as db:
            with db.begin():
                db.execute(text("SET TRANSACTION READ ONLY"))
                db.execute(text("SET LOCAL statement_timeout = '15s'"))
                report = inventory(db)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0
    except Exception as error:
        print(f"CREDIT_AUDIT=FAILED TYPE={type(error).__name__}; no changes applied")
        return 1
    finally:
        if engine is not None:
            engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
