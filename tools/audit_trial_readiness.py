"""Office-only, read-only readiness inventory. Never print configuration values."""
import argparse
import importlib.util
import json
import sys
from pathlib import Path
from urllib.parse import urlsplit

from sqlalchemy import func, inspect, select, text
from sqlalchemy.orm import Session

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from qd766.backend.config import Settings, load_environment_file
from qd766.backend.database import create_database_engine
from qd766.backend.models import (
    Dataset, NationalSummarySnapshot, ProvinceCollectionBatch,
    ProvinceCollectionBatchItem, Snapshot,
)


def configuration_checks(settings):
    try:
        dependency = importlib.util.find_spec("google.oauth2.id_token") is not None
    except ModuleNotFoundError:
        dependency = False
    uri = urlsplit(settings.google_redirect_uri)
    return {
        "googleClientConfigured": bool(settings.google_client_id and settings.google_client_secret),
        "googleRedirectHTTPS": uri.scheme == "https" and bool(uri.hostname)
        and uri.path == "/api/v1/auth/google/callback"
        and not (uri.username or uri.password or uri.query or uri.fragment),
        "googleVerificationDependency": dependency,
        "publicBoundaryEnabled": settings.public_read_only,
        "loginRequired": settings.require_login,
        "paidRequestsEnabled": settings.paid_requests_enabled,
        "positiveCreditPriceConfigured": settings.formality_credit_cost > 0,
        "trialCreditsEnabled": settings.trial_credits_enabled,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--year", type=int, required=True)
    args = parser.parse_args()
    if (ROOT / ".env").exists():
        load_environment_file(ROOT / ".env")
    settings = Settings.from_env()
    report = {"readOnly": True, "year": args.year,
              "configuration": configuration_checks(settings)}
    engine = create_database_engine(settings)
    try:
        with engine.connect().execution_options(isolation_level="REPEATABLE READ") as conn:
            with conn.begin():
                conn.execute(text("SET TRANSACTION READ ONLY"))
                tables = set(inspect(conn).get_table_names())
                required = {"user_accounts", "login_attempts", "login_sessions",
                            "paid_data_requests", "credit_ledger_entries", "user_notifications"}
                report["accountSchema"] = {"state": "PASS" if required <= tables else "BLOCKED",
                                          "missingTables": sorted(required - tables)}
                with Session(bind=conn, autoflush=False) as db:
                    latest = {}
                    for row in db.scalars(select(NationalSummarySnapshot).where(
                        NationalSummarySnapshot.year == args.year
                    ).order_by(NationalSummarySnapshot.captured_at.desc())):
                        key = (row.period_type, row.period_value)
                        if key not in latest:
                            latest[key] = {"periodType": row.period_type, "periodValue": row.period_value,
                                "provinceCount": row.province_count, "groupCount": row.group_count,
                                "completeness": row.completeness_state, "capturedAt": row.captured_at.isoformat()}
                    report["nationalSummaries"] = list(latest.values())
                    coverage = db.execute(select(Snapshot.root_department_id,
                        func.count(func.distinct(Dataset.group_name))).join(Dataset).where(
                        Snapshot.scope == "all", Snapshot.state == "complete",
                        Snapshot.period_type == "year", Snapshot.year == args.year
                    ).group_by(Snapshot.root_department_id)).all()
                    report["annualDetails"] = {"storedProvinces": len(coverage),
                        "sixDatasetProvinces": sum(count == 6 for _, count in coverage),
                        "note": "Six datasets do not prove every agency has every score."}
                    batch = db.scalar(select(ProvinceCollectionBatch).where(
                        ProvinceCollectionBatch.period_type == "year",
                        ProvinceCollectionBatch.year == args.year
                    ).order_by(ProvinceCollectionBatch.created_at.desc()).limit(1))
                    report["latestAnnualBatch"] = None if batch is None else {
                        "id": str(batch.id), "state": batch.state, "total": batch.total_items,
                        "states": dict(db.execute(select(ProvinceCollectionBatchItem.state,
                            func.count()).where(ProvinceCollectionBatchItem.batch_id == batch.id
                            ).group_by(ProvinceCollectionBatchItem.state)).all())}
    except Exception as error:
        # Connection errors can contain a credential-bearing URL: never serialize them.
        report["databaseAudit"] = {"state": "BLOCKED", "errorType": type(error).__name__}
    finally:
        engine.dispose()
    print(json.dumps(report, ensure_ascii=True))


if __name__ == "__main__":
    main()
