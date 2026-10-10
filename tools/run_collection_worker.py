#!/usr/bin/env python3
"""Run the sequential QĐ766 collection worker.

The worker is safe to leave running while the collection circuit is open:
``run_one_job`` checks the PostgreSQL circuit before claiming a job or calling
the upstream transport.
"""
from __future__ import annotations

import argparse
import json
import os
import socket
import sys
import time
from sqlalchemy.exc import SQLAlchemyError
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from qd766.backend.config import Settings, load_environment_file
from qd766.backend.database import create_database_engine, create_session_factory
from qd766.backend.worker import EvaluationSnapshotProcessor, run_one_job
from qd766.backend.jobs import WorkerLeaseLost
from qd766.collection import UrllibTransport


def _collection_root() -> Path:
    configured = os.getenv("QD766_COLLECTION_ROOT")
    if configured:
        return Path(configured)
    return ROOT.parent / "data" / "collections"


def _event(state: str, job_id: object = None, duration_seconds: float | None = None) -> str:
    return json.dumps(
        {
            "event": "worker-state",
            "state": state,
            "jobId": str(job_id) if job_id else None,
            "at": datetime.now(timezone.utc).isoformat(),
            "durationSeconds": round(duration_seconds, 3) if duration_seconds is not None else None,
        },
        ensure_ascii=False,
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true", help="Check/process at most one job")
    parser.add_argument("--poll-seconds", type=float, default=15.0)
    parser.add_argument("--controlled", action="store_true", help="Opt into pooled 3-request collection; no scheduler/task changes")
    arguments = parser.parse_args()
    if arguments.poll_seconds < 1:
        parser.error("--poll-seconds must be at least 1")

    load_environment_file(ROOT / ".env")
    engine = create_database_engine(Settings.from_env())
    factory = create_session_factory(engine)
    worker_id = f"{socket.gethostname()}:{os.getpid()}"
    if arguments.controlled:
        from qd766.concurrent_collection import PooledHttpTransport
        from qd766.backend.jobs import renew_worker_lease
        def guard():
            with factory.begin() as db:
                renew_worker_lease(db, worker_id)
        transport = PooledHttpTransport(max_workers=3, spacing=0.4, guard=guard)
    else:
        transport = UrllibTransport(timeout_seconds=45)
    processor = EvaluationSnapshotProcessor(
        collection_root=_collection_root(),
        transport=transport,
        minimum_delay_seconds=5,
        jitter_seconds=1,
        max_retries=4 if arguments.controlled else 1,
        max_workers=3 if arguments.controlled else 1,
    )
    worker_id = f"{socket.gethostname()}:{os.getpid()}"
    previous_idle_state: str | None = None
    database_failures = 0
    try:
        while True:
            started = time.monotonic()
            try:
                result = run_one_job(factory, processor, worker_id=worker_id)
                database_failures = 0
            except SQLAlchemyError as error:
                # Never log connection strings/SQL parameters or spin on outages.
                database_failures += 1
                delay = min(60, 5 * 2 ** min(database_failures - 1, 4))
                print(json.dumps({'event':'worker-database-retry', 'errorType':type(error).__name__,
                                  'delaySeconds':delay}), flush=True)
                if arguments.once:
                    return 1
                time.sleep(delay)
                continue
            except WorkerLeaseLost:
                print(_event('lease-lost'), flush=True)
                if arguments.once:
                    return 0
                time.sleep(arguments.poll_seconds)
                continue
            state = result.state if result else "idle"
            if result and result.job_id is not None:
                print(_event(state, result.job_id, time.monotonic() - started), flush=True)
                previous_idle_state = None
            elif state != previous_idle_state:
                print(_event(state), flush=True)
                previous_idle_state = state
            if arguments.once:
                return 0
            time.sleep(2.5 if arguments.controlled and result and result.job_id is not None else arguments.poll_seconds)
    except KeyboardInterrupt:
        print(_event("stopped"), flush=True)
        return 0
    finally:
        if arguments.controlled:
            transport.close()
        engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
