"""Import one complete normalized M1 snapshot into PostgreSQL."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from qd766.backend.config import Settings
from qd766.backend.database import create_database_engine, create_session_factory
from qd766.backend.importer import SnapshotImportError, store_normalized_snapshot


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("snapshot", type=Path)
    args = parser.parse_args()
    try:
        payload = json.loads(args.snapshot.read_text(encoding="utf-8"))
        factory = create_session_factory(create_database_engine(Settings.from_env()))
        with factory.begin() as session:
            snapshot = store_normalized_snapshot(session, payload)
        print(json.dumps({"result": "PASS", "snapshotId": str(snapshot.id)}))
        return 0
    except (OSError, json.JSONDecodeError, SnapshotImportError) as error:
        print(json.dumps({"result": "FAIL", "error": str(error)}), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
