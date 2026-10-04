"""Real-wallet API/worker/scheduler integration in a new isolated PG test schema.

Google identity and worker payload are mocked. No HTTP server or DVCQG transport.
The restored public schema is checked read-only and fingerprinted before/after.
"""
import argparse
import io
import sys
import time
import unittest
import uuid
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import create_engine, select, func, text

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))
sys.path.insert(0,str(ROOT/"tests"))
from rehearse_credit_restore import restore_url, fingerprint
from qd766.backend.public_deployment import read_config, WEBSITE_CALLBACK
from qd766.backend.database import create_session_factory
from qd766.backend.wallet_runtime import verify_real_wallet_schema
from qd766.backend.app import create_app
from qd766.backend.models import UserAccount, CreditWalletEvent
from qd766.backend.credit_wallet import grant, reserve, balance
from qd766.backend.wallet_access import enroll
from qd766.backend.subscriptions import schedule_plan
from qd766.backend.subscription_maintenance import run_subscription_maintenance
from test_trial_journey import TrialJourneyTests, ROOT as MOCK_ROOT


class RealWalletIntegration(TrialJourneyTests):
    real_wallet_runtime=True
    origin="https://bochiso766.com"
    runtime_url=None
    schema_engine=None

    def setUp(self):
        def real_app(settings):
            configured=replace(settings, database_url=self.runtime_url, real_wallet_enabled=True,
                source_wallet_trial=False, local_google_trial=False, google_redirect_uri=WEBSITE_CALLBACK)
            # Test binding only: production engine always fixes search_path=public.
            with patch("qd766.backend.app.create_database_engine",return_value=self.schema_engine):
                return create_app(configured)
        with patch("test_trial_journey.create_app",side_effect=real_app):
            super().setUp()
        self.admin.__enter__()  # Actual lifespan + read-only public-schema gate + cycle loop.
        self.addCleanup(self.admin.__exit__,None,None,None)
        deadline=time.monotonic()+5
        while self.app.state.credit_cycle_maintenance["runs"] < 1 and time.monotonic() < deadline:
            time.sleep(.01)
        self.assertGreaterEqual(self.app.state.credit_cycle_maintenance["runs"],1)
        self.assertEqual(self.app.state.credit_cycle_maintenance["state"],"ok")
        self.assertTrue(self.app.state.settings.real_wallet_enabled)
        self.assertFalse(self.app.state.settings.source_wallet_trial)
        self.assertFalse(self.app.state.settings.local_google_trial)

    def tearDown(self):
        # Stop background transactions before disposing the shared engine.
        self.doCleanups()
        super().tearDown()

    def test_complete_trial_journey(self):
        super().test_complete_trial_journey()
        now=datetime.now(timezone.utc)
        aid=uuid.uuid4()
        with self.factory.begin() as db:
            db.add(UserAccount(id=aid, external_subject="integration-cycle:"+uuid.uuid4().hex,
                display_name="Cycle test",trial_admitted=True,root_department_id=MOCK_ROOT))
            db.flush()
            enroll(db,aid,now=now)
            grant(db,aid,100,source="subscription",operation_key="expired",now=now-timedelta(days=2),
                expires_at=now-timedelta(days=1))
            grant(db,aid,70,source="purchased",operation_key="carry",now=now)
            reserve(db,aid,5,request_key="held-at-expiry",now=now-timedelta(days=2))
            schedule_plan(db,aid,tier="province",origin="trial",operation_key="current",
                starts_at=now,months=1,now=now)
        initial_runs=self.app.state.credit_cycle_maintenance["runs"]
        print("WAITING_FOR_REAL_60_SECOND_CYCLE no_user_request_required",flush=True)
        deadline=time.monotonic()+70
        while self.app.state.credit_cycle_maintenance["runs"]<=initial_runs and time.monotonic()<deadline:
            time.sleep(.1)
        status=self.app.state.credit_cycle_maintenance
        self.assertGreater(status["runs"],initial_runs)
        self.assertEqual(status["state"],"ok")
        self.assertEqual((status["grantedCycles"],status["expiredCredit"]),(1,95))
        first=run_subscription_maintenance(self.factory,now=now)
        second=run_subscription_maintenance(self.factory,now=now)
        self.assertEqual(first["failures"],[])
        self.assertEqual((first["grantedCycles"],first["expiredCredit"]),(0,0))
        self.assertEqual((second["grantedCycles"],second["expiredCredit"]),(0,0))
        with self.factory() as db:
            self.assertEqual(balance(db,aid,now=now),dict(subscription=100,purchased=70,reserved=5,available=170))
            self.assertEqual(db.scalar(select(func.count()).select_from(CreditWalletEvent).where(
                CreditWalletEvent.account_id==aid,CreditWalletEvent.kind=="expire")),1)
        self.assertEqual(self.admin.get("/api/v1/health/ready").status_code,200)
        # Operations API remains forbidden even to the test administrator.
        self.assertEqual(self.admin.post("/api/v1/collection-control",json={}).status_code,403)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database",required=True)
    parser.add_argument("--connection-file",type=Path,required=True)
    args=parser.parse_args()
    engine=None
    schema_engine=None
    try:
        url=restore_url(read_config(args.connection_file),args.database)
        engine=create_engine(url,connect_args={"connect_timeout":5,"options":"-c search_path=public"})
        verify_real_wallet_schema(create_session_factory(engine))
        before=fingerprint(engine)
        schema="real_wallet_integration_"+uuid.uuid4().hex
        with engine.begin() as db:
            db.execute(text(f'CREATE SCHEMA "{schema}"'))
        print("TEST_SCHEMA="+schema+" retained; mock accounts only",flush=True)
        schema_engine=create_engine(url,connect_args={"connect_timeout":5,
            "options":f"-c search_path={schema} -c lock_timeout=10000 -c statement_timeout=20000"})
        RealWalletIntegration.runtime_url=url.render_as_string(hide_password=False)
        RealWalletIntegration.schema_engine=schema_engine
        suite=unittest.TestSuite([RealWalletIntegration("test_complete_trial_journey")])
        output=io.StringIO()
        result=unittest.TextTestRunner(stream=output).run(suite)
        if fingerprint(engine)!=before:
            raise AssertionError("Restored public rows changed")
        if not result.wasSuccessful():
            # Never echo traceback / SQL values / Google session identifiers.
            print(f"REAL_WALLET_INTEGRATION=FAIL errors={len(result.errors)} failures={len(result.failures)}")
            return 1
        print("REAL_WALLET_INTEGRATION=PASS API_WORKER_SETTLEMENT CYCLE_LIFESPAN CYCLE_MAINTENANCE")
        print("PUBLIC_ROWS=UNCHANGED GOOGLE=MOCK WORKER_DATA=MOCK NO_NETWORK_SERVER NO_DVCQG NO_PRODUCTION_CHANGES")
        return 0
    except Exception as error:
        print("REAL_WALLET_INTEGRATION=FAIL TYPE="+type(error).__name__+"; no production fallback")
        return 1
    finally:
        if schema_engine is not None:schema_engine.dispose()
        if engine is not None:engine.dispose()


if __name__=="__main__":raise SystemExit(main())
