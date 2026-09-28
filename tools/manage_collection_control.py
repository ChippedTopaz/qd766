#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from qd766.backend.config import Settings, load_environment_file
from qd766.backend.database import create_database_engine, create_session_factory
from qd766.backend.jobs import close_collection_circuit
from qd766.backend.models import CollectionControl


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("status", "close"))
    parser.add_argument(
        "--confirm-reviewed",
        action="store_true",
        help="Required to close the circuit after an operator reviews the probe.",
    )
    arguments = parser.parse_args()
    if arguments.action == "close" and not arguments.confirm_reviewed:
        parser.error("close requires --confirm-reviewed")

    load_environment_file(ROOT / ".env")
    engine = create_database_engine(Settings.from_env())
    factory = create_session_factory(engine)
    try:
        if arguments.action == "close":
            with factory.begin() as session:
                close_collection_circuit(session)
        with factory() as session:
            control = session.get(CollectionControl, "dvcqg")
            if control is None:
                print(json.dumps({"key": "dvcqg", "state": "not-initialized"}))
                return 1
            print(
                json.dumps(
                    {
                        "key": control.key,
                        "circuitState": control.circuit_state,
                        "reason": control.reason,
                        "openedAt": control.opened_at.isoformat() if control.opened_at else None,
                        "leaseLockedBy": control.lease_locked_by,
                        "action": arguments.action,
                    },
                    ensure_ascii=False,
                    indent=2,
                )
            )
        return 0
    finally:
        engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
