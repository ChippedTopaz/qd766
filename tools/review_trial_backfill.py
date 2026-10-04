"""Read-only backfill review on a restored DB. Never activates accounts."""
import argparse
import json
import sys
from pathlib import Path
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))
from rehearse_credit_restore import restore_url
from qd766.backend.public_deployment import read_config
from qd766.backend.database import create_session_factory
from qd766.backend.wallet_runtime import verify_real_wallet_schema
from qd766.backend.models import UserAccount
from qd766.backend.trial_backfill import review


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database",required=True)
    parser.add_argument("--connection-file",type=Path,required=True)
    args=parser.parse_args()
    engine=None
    try:
        url=restore_url(read_config(args.connection_file),args.database)
        engine=create_engine(url,connect_args={"connect_timeout":5,"options":"-c search_path=public"})
        verify_real_wallet_schema(create_session_factory(engine))
        with Session(engine) as db:
            db.execute(text("SET TRANSACTION READ ONLY"))
            db.execute(text("SET LOCAL statement_timeout = '15s'"))
            rows=[review(db,account)[0] for account in db.scalars(select(UserAccount).order_by(UserAccount.id))]
        print(json.dumps({"mode":"REVIEW_ONLY_NO_ACTIVATION","accounts":rows,
            "eligible":sum(row["eligible"] for row in rows)},ensure_ascii=False,indent=2))
        return 0
    except Exception as error:
        print("BACKFILL_REVIEW=FAILED TYPE="+type(error).__name__+"; no changes applied")
        return 1
    finally:
        if engine is not None:engine.dispose()


if __name__=="__main__":raise SystemExit(main())
