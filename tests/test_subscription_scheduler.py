import asyncio
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from qd766.backend.subscription_scheduler import local_credit_lifespan, maintenance_loop


def result(failures=None):
    return dict(processed=3, grantedCycles=0, expiredCredit=0, failures=failures or [])


class SchedulerTests(unittest.IsolatedAsyncioTestCase):
    async def test_real_schema_gate_failure_starts_no_maintenance(self):
        from test_wallet_runtime import real_settings
        app=SimpleNamespace(state=SimpleNamespace(settings=real_settings(),session_factory=object()))
        with patch("qd766.backend.wallet_runtime.verify_real_wallet_schema",side_effect=ValueError("Old schema")):
            with patch("qd766.backend.subscription_scheduler.run_subscription_maintenance") as runner:
                with self.assertRaises(ValueError):
                    async with local_credit_lifespan(app):
                        self.fail("Unverified schema must not serve")
                runner.assert_not_called()

    async def test_explicit_real_runtime_uses_separate_logs_after_schema_check(self):
        from test_wallet_runtime import real_settings
        called=asyncio.Event()
        loop=asyncio.get_running_loop()
        app=SimpleNamespace(state=SimpleNamespace(settings=real_settings(),session_factory=object()))
        def run(*args, **kwargs):
            loop.call_soon_threadsafe(called.set)
            return result()
        with patch("qd766.backend.wallet_runtime.verify_real_wallet_schema") as verify:
            with patch("qd766.backend.subscription_scheduler.run_subscription_maintenance",side_effect=run):
                with self.assertLogs("uvicorn.error",level="INFO") as logs:
                    async with local_credit_lifespan(app):
                        await asyncio.wait_for(called.wait(),1)
        verify.assert_called_once_with(app.state.session_factory)
        self.assertIn("REAL_CREDIT_CYCLES_ENABLED", " ".join(logs.output))
        self.assertNotIn("LOCAL_CREDIT", " ".join(logs.output))

    async def test_disabled_for_production_or_non_source_wallet(self):
        for local, wallet in ((False, False), (False, True), (True, False)):
            app=SimpleNamespace(state=SimpleNamespace(settings=SimpleNamespace(
                local_google_trial=local, source_wallet_trial=wallet)))
            with patch("qd766.backend.subscription_scheduler.run_subscription_maintenance") as runner:
                async with local_credit_lifespan(app):
                    await asyncio.sleep(0)
                runner.assert_not_called()
                self.assertFalse(hasattr(app.state,"credit_cycle_maintenance"))

    async def test_first_tick_without_user_request_and_clean_shutdown(self):
        called=asyncio.Event()
        loop=asyncio.get_running_loop()
        factory=object()
        app=SimpleNamespace(state=SimpleNamespace(settings=SimpleNamespace(
            local_google_trial=True,source_wallet_trial=True),session_factory=factory))
        def run(received, *, now):
            self.assertIs(received,factory)
            self.assertIsNotNone(now.tzinfo)
            loop.call_soon_threadsafe(called.set)
            return result()
        with patch("qd766.backend.subscription_scheduler.run_subscription_maintenance",side_effect=run):
            async with local_credit_lifespan(app):
                await asyncio.wait_for(called.wait(),1)
        self.assertEqual(app.state.credit_cycle_maintenance["runs"],1)
        self.assertEqual(app.state.credit_cycle_maintenance["state"],"stopped")

    async def test_partial_failure_retries_and_logs_only_changes_then_recovery(self):
        stop=asyncio.Event()
        status={}
        loop=asyncio.get_running_loop()
        count=0
        now=datetime(2026,10,4,tzinfo=timezone.utc)
        def run(*args,**kwargs):
            nonlocal count
            count+=1
            self.assertEqual(kwargs["now"],now)
            if count<3:
                return result([{"accountId":"PRIVATE_ID","type":"OperationalError"}])
            loop.call_soon_threadsafe(stop.set)
            return result()
        with patch("qd766.backend.subscription_scheduler.run_subscription_maintenance",side_effect=run):
            with self.assertLogs("uvicorn.error",level="INFO") as logs:
                await asyncio.wait_for(maintenance_loop(object(),stop,status,
                    interval_seconds=.001,clock=lambda:now),1)
        self.assertEqual(status["runs"],3)
        self.assertEqual(status["failedAccounts"],0)
        self.assertEqual(len(logs.output),2)
        self.assertIn("FAILED",logs.output[0])
        self.assertIn("RECOVERED",logs.output[1])
        self.assertNotIn("PRIVATE_ID"," ".join(logs.output))

    async def test_exception_does_not_terminate_loop_or_leak_message(self):
        stop=asyncio.Event()
        status={}
        loop=asyncio.get_running_loop()
        count=0
        def run(*args,**kwargs):
            nonlocal count
            count+=1
            if count==1:
                raise RuntimeError("private connection details")
            loop.call_soon_threadsafe(stop.set)
            return result()
        with patch("qd766.backend.subscription_scheduler.run_subscription_maintenance",side_effect=run):
            with self.assertLogs("uvicorn.error",level="INFO") as logs:
                await asyncio.wait_for(maintenance_loop(object(),stop,status,interval_seconds=.001),1)
        self.assertEqual(status["runs"],2)
        self.assertNotIn("private connection details"," ".join(logs.output))


if __name__ == "__main__":
    unittest.main()
