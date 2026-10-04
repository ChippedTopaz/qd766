"""Run mocked invite-to-library API journey in a new test schema only."""
import argparse
import io
import sys
import unittest
import uuid
from datetime import datetime, timezone
from pathlib import Path
from sqlalchemy import create_engine, text

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"tests"))
from test_postgresql_credits import isolated_url
from test_trial_journey import TrialJourneyTests


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--connection-file",type=Path,required=True)
    args=parser.parse_args()
    try:
        url=isolated_url(args.connection_file)
        schema="journey_"+datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_")+uuid.uuid4().hex[:8]
        engine=create_engine(url,connect_args={"connect_timeout":5})
        try:
            with engine.begin() as db:db.execute(text(f'CREATE SCHEMA "{schema}"'))
        finally:engine.dispose()
        print(f"TEST_SCHEMA={schema} retained for inspection",flush=True)
        TrialJourneyTests.database_url=url.update_query_dict({"options":f"-c search_path={schema} -c lock_timeout=10000 -c statement_timeout=20000",
            "connect_timeout":"5"}).render_as_string(hide_password=False)
        output=io.StringIO()
        suite=unittest.TestSuite([TrialJourneyTests("test_complete_trial_journey")])
        result=unittest.TextTestRunner(stream=output).run(suite)
        if not result.wasSuccessful():
            # Do not emit tracebacks that can contain database URLs or SQL values.
            print(f"TRIAL_JOURNEY=FAIL errors={len(result.errors)} failures={len(result.failures)}")
            return 1
        print("TRIAL_JOURNEY=PASS GOOGLE=MOCK DATA=SIMULATED NO_DVCQG_CALLS NO_PRODUCTION_DB")
        return 0
    except Exception as error:
        print(f"TRIAL_JOURNEY=FAIL TYPE={type(error).__name__}; no production fallback")
        return 1


if __name__=="__main__":raise SystemExit(main())
