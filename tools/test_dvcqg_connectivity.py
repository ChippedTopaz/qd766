#!/usr/bin/env python3
"""One-shot, read-only DVCQG connectivity probe. Never POSTs or retries."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from qd766.backend.config import Settings, load_environment_file
from qd766.backend.connectivity import probe_dvcqg_connectivity
from qd766.backend.database import create_database_engine, create_session_factory
from qd766.backend.jobs import open_collection_circuit


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--record-control",
        action="store_true",
        help="Open the PostgreSQL circuit breaker when the probe returns a stop signal.",
    )
    arguments = parser.parse_args()
    result = probe_dvcqg_connectivity()
    payload = result.to_dict()

    if arguments.record_control and not result.safe_to_review_for_reenable:
        load_environment_file(ROOT / ".env")
        engine = create_database_engine(Settings.from_env())
        factory = create_session_factory(engine)
        try:
            with factory.begin() as session:
                open_collection_circuit(
                    session,
                    reason="connectivity-probe-stop",
                    detail={
                        "kind": result.stop_reason,
                        "retryable": False,
                        "httpStatus": result.http_status,
                        "errorType": result.error_type,
                        "message": result.error_message,
                    },
                )
            payload["circuitAction"] = "opened"
        finally:
            engine.dispose()
    else:
        payload["circuitAction"] = "unchanged"

    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if result.safe_to_review_for_reenable else 2


if __name__ == "__main__":
    raise SystemExit(main())
