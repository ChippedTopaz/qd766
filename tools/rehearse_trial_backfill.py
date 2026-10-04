"""Rehearse old-account activation on restored public data, then rollback all writes."""
import argparse
import sys
import uuid
from datetime import datetime,timezone
from pathlib import Path
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))
from rehearse_credit_restore import restore_url,fingerprint
from qd766.backend.public_deployment import read_config
from qd766.backend.database import create_session_factory
from qd766.backend.wallet_runtime import verify_real_wallet_schema
from qd766.backend.models import UserAccount
from qd766.backend.trial_backfill import review,apply_selected
from qd766.backend.credit_wallet import balance


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
        before=fingerprint(engine)
        count=0
        with engine.connect() as connection:
            transaction=connection.begin()
            try:
                with Session(bind=connection,info={"real_wallet_enabled":True,"source_wallet_enabled":True}) as db:
                    owner=db.scalar(select(UserAccount).where(UserAccount.email=="vietnt89@gmail.com",
                        UserAccount.role=="admin",UserAccount.active.is_(True)))
                    if owner is None:raise ValueError("Verified owner required")
                    selected=[a.id for a in db.scalars(select(UserAccount)) if review(db,a)[0]["eligible"]]
                    if not selected:raise ValueError("No eligible accounts to rehearse")
                    now=datetime.now(timezone.utc)
                    operation=uuid.uuid4()
                    first=apply_selected(db,account_ids=selected,administrator_id=owner.id,operation_id=operation,now=now)
                    second=apply_selected(db,account_ids=selected,administrator_id=owner.id,operation_id=operation,now=now)
                    if first!={"activated":len(selected),"replayed":False} or second!={"activated":0,"replayed":True}:
                        raise AssertionError("Activation replay differs")
                    if any(balance(db,aid,now=now)["available"]!=100 for aid in selected):
                        raise AssertionError("Trial grant differs from 100")
                    count=len(selected)
            finally:
                if transaction.is_active:transaction.rollback()
        if fingerprint(engine)!=before:raise AssertionError("Restored public data changed after rollback")
        print(f"BACKFILL_REHEARSAL=PASS ELIGIBLE={count} CREDIT_PER_TRIAL=100 REPLAY_GRANTS=0 ROLLBACK_VERIFIED")
        print("NO_REAL_ACTIVATION NO_PRODUCTION_CHANGES NO_SERVICE_STARTED")
        return 0
    except Exception as error:
        print("BACKFILL_REHEARSAL=FAILED TYPE="+type(error).__name__+"; no production fallback")
        return 1
    finally:
        if engine is not None:engine.dispose()


if __name__=="__main__":raise SystemExit(main())
