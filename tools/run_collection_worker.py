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
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from qd766.backend.config import Settings, load_environment_file
from qd766.backend.database import create_database_engine, create_session_factory
from qd766.backend.worker import EvaluationSnapshotProcessor, run_one_job
from qd766.collection import UrllibTransport


def _collection_root() -> Path:
    configured = os.getenv("QD766_COLLECTION_ROOT")
    if configured:
        return Path(configured)
    return ROOT.parent / "data" / "collections"


def _event(state: str, job_id: object = None) -> str:
    return json.dumps(
        {
            "event": "worker-state",
            "state": state,
            "jobId": str(job_id) if job_id else None,
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
        from qd766.backend.models import CollectionControl
        from qd766.collection import SafetyStop
        def guard():
            with factory() as db:
                control=db.get(CollectionControl,'dvcqg')
                if control is None or control.circuit_state!='closed' or control.lease_locked_by!=worker_id:
                    raise SafetyStop('Collection control changed')
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
    try:
        while True:
            result = run_one_job(factory, processor, worker_id=worker_id)
            state = result.state if result else "idle"
            if result and result.job_id is not None:
                print(_event(state, result.job_id), flush=True)
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
