"""Process approved Credit cycles only in explicitly enabled wallet instances.

No collection worker, payment, enrollment or trial creation. Clean shutdown
waits for the current transaction batch rather than abandoning a running thread.
"""
import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from .subscription_maintenance import run_subscription_maintenance

logger = logging.getLogger("uvicorn.error")


async def maintenance_loop(factory, stop, status, *, interval_seconds=60, clock=None, log_prefix="LOCAL_CREDIT_CYCLES"):
    if interval_seconds <= 0:
        raise ValueError("Maintenance interval must be positive")
    clock = clock or (lambda: datetime.now(timezone.utc))
    last_failure = None
    while not stop.is_set():
        now = clock()
        status.update(state="running", lastRunAt=now.isoformat())
        try:
            result = await asyncio.to_thread(run_subscription_maintenance, factory, now=now)
            failure = tuple(sorted(item["type"] for item in result["failures"])) or None
            status.update(state="degraded" if failure else "ok", runs=status.get("runs", 0)+1,
                processed=result["processed"], grantedCycles=result["grantedCycles"],
                expiredCredit=result["expiredCredit"], failedAccounts=len(result["failures"]))
            if status["runs"] == 1 and not failure:
                logger.info("%s_READY accounts=%s", log_prefix, result["processed"])
            if result["grantedCycles"] or result["expiredCredit"]:
                logger.info("%s grants=%s expired=%s", log_prefix,
                            result["grantedCycles"], result["expiredCredit"])
        except Exception as error:
            failure = (type(error).__name__,)
            status.update(state="failed", runs=status.get("runs", 0)+1)
        if failure != last_failure:
            if failure:
                # Never log secrets, account data, SQL or exception messages.
                logger.warning("%s_FAILED types=%s", log_prefix, ",".join(sorted(set(failure))))
            elif last_failure:
                logger.info("%s_RECOVERED", log_prefix)
        last_failure = failure
        try:
            await asyncio.wait_for(stop.wait(), timeout=interval_seconds)
        except TimeoutError:
            pass
    status["state"] = "stopped"


@asynccontextmanager
async def local_credit_lifespan(app):
    settings = app.state.settings
    real = getattr(settings, "real_wallet_enabled", False)
    if not (real or (settings.local_google_trial and settings.source_wallet_trial)):
        yield
        return
    if real:
        from .wallet_runtime import validate_wallet_runtime, verify_real_wallet_schema
        validate_wallet_runtime(settings)
        await asyncio.to_thread(verify_real_wallet_schema, app.state.session_factory)
    stop = asyncio.Event()
    analysis_tasks=[]
    if getattr(settings,'gemini_queue_enabled',False):
        from .analysis_queue import verify_schema,worker_loop
        await asyncio.to_thread(verify_schema,app.state.engine)
        analysis_tasks=[asyncio.create_task(worker_loop(app.state.session_factory,settings,stop),
            name='analysis-queue-'+str(index)) for index in range(2)]
        logger.info('ANALYSIS_QUEUE_ENABLED workers=2 waiting_limit=20 wait_minutes=10')
    app.state.credit_cycle_maintenance = {"state": "starting", "runs": 0}
    prefix = "REAL_CREDIT_CYCLES" if real else "LOCAL_CREDIT_CYCLES"
    task = asyncio.create_task(maintenance_loop(app.state.session_factory, stop,
        app.state.credit_cycle_maintenance, log_prefix=prefix), name="credit-cycles")
    logger.info("%s_ENABLED interval=60s no_collection_worker", prefix)
    try:
        yield
    finally:
        stop.set()
        await task
        await asyncio.gather(*analysis_tasks)
