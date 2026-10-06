"""Read-only by default; explicitly reconcile stale AI holds, not TTHC jobs."""
import argparse,sys
from pathlib import Path
from datetime import datetime,timedelta,timezone
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from sqlalchemy import select,inspect
from qd766.backend.config import Settings,load_environment_file
from qd766.backend.database import create_database_engine,create_session_factory
from qd766.backend.models import GeminiAnalysis
from qd766.backend.analysis import recover_interrupted
from qd766.backend.paid_requests import _locked_account

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--env-file',type=Path,required=True)
    parser.add_argument('--confirm-refunds',action='store_true');args=parser.parse_args()
    load_environment_file(args.env_file.resolve(strict=True));engine=create_database_engine(Settings.from_env())
    try:
        if not inspect(engine).has_table('gemini_analyses'):raise SystemExit('ANALYSIS_SCHEMA_NOT_INSTALLED')
        factory=create_session_factory(engine);now=datetime.now(timezone.utc)
        with factory() as db:
            accounts=list(db.scalars(select(GeminiAnalysis.account_id).where(GeminiAnalysis.state=='running',
                GeminiAnalysis.created_at<now-timedelta(minutes=5)).distinct()))
        print('STALE_ANALYSIS_ACCOUNTS='+str(len(accounts)))
        if not args.confirm_refunds:print('READ_ONLY_NO_CHANGES');return
        for aid in accounts:
            with factory.begin() as db:
                _locked_account(db,aid);recover_interrupted(db,aid,now)
        print('ANALYSIS_REFUNDS_RECONCILED')
    finally:engine.dispose()

if __name__=='__main__':main()
