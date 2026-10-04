"""Compare configured DB targets only; cannot attest running process settings."""
import argparse
import sys
from pathlib import Path
from sqlalchemy.engine import make_url

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from qd766.backend.config import Settings, load_environment_file
from qd766.backend.public_deployment import public_settings, read_config


def target(url):
    value = make_url(url)
    host = "loopback" if value.host in {"localhost", "127.0.0.1", "::1"} else value.host
    return value.drivername, host, value.port or 5432, value.database, dict(value.query)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--office-file", type=Path, required=True)
    parser.add_argument("--public-file", type=Path, required=True)
    args = parser.parse_args()
    try:
        public = public_settings(read_config(args.office_file), read_config(args.public_file))
        load_environment_file(args.office_file)
        worker = Settings.from_env()
        match = target(public.database_url) == target(worker.database_url)
        print("CONFIG_DATABASE_ALIGNMENT=" + ("MATCH" if match else "MISMATCH"))
        print("CONFIG_ONLY_DEFAULT_REAL_WALLET=" + str(public.real_wallet_enabled) + " (NOT_RUNNING_BACKEND_MODE)")
        print("RUNNING_PROCESSES=NOT_VERIFIED NO_DB_CONNECTION NO_CHANGES")
        return 0 if match else 1
    except Exception as error:
        print(f"CONFIG_DATABASE_ALIGNMENT=UNKNOWN TYPE={type(error).__name__}; no secret output")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
