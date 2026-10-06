"""Upgrade ONLY the Google mock trial in qd766_credit_test, never office DB."""
import argparse,sys
from pathlib import Path
from sqlalchemy import create_engine,text,inspect
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from test_postgresql_credits import isolated_url
from qd766.backend.models import AnalysisQueueEntry
from qd766.backend.analysis_queue import verify_schema

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--confirm',action='store_true');args=parser.parse_args()
    if not args.confirm:print('PLAN_ONLY_NO_DATABASE_CONNECTION');return
    url=isolated_url(ROOT/'.env');assert url.database=='qd766_credit_test'
    engine=create_engine(url,connect_args={'connect_timeout':5,'options':'-c search_path=credit_google_trial -c lock_timeout=5000'})
    try:
        with engine.begin() as connection:
            if connection.scalar(text('SELECT current_schema()'))!='credit_google_trial':raise SystemExit('LOCAL_TRIAL_SCHEMA_REQUIRED')
            if connection.scalar(text("SELECT count(*) FROM gemini_analyses WHERE state IN ('queued','running')")):
                raise SystemExit('LOCAL_PENDING_ANALYSES_MUST_FINISH_FIRST')
            constraint=next(c for c in inspect(connection).get_check_constraints('gemini_analyses') if c['name']=='ck_gemini_analysis_state')
            if 'queued' not in constraint['sqltext']:
                connection.execute(text('ALTER TABLE gemini_analyses DROP CONSTRAINT ck_gemini_analysis_state'))
                connection.execute(text("ALTER TABLE gemini_analyses ADD CONSTRAINT ck_gemini_analysis_state CHECK (state IN ('queued','running','ready','failed','cancelled'))"))
            connection.execute(text('CREATE INDEX IF NOT EXISTS ix_gemini_analysis_queue ON gemini_analyses (state,created_at,id)'))
            AnalysisQueueEntry.__table__.create(connection,checkfirst=True)
        verify_schema(engine);print('LOCAL_ANALYSIS_QUEUE_READY test_database=qd766_credit_test schema=credit_google_trial')
    finally:engine.dispose()

if __name__=='__main__':main()
