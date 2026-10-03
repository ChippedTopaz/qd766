"""Apply the additive trial migration after an externally verified database backup."""
import argparse
import hashlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from alembic import command
from alembic.config import Config
from qd766.backend.config import load_environment_file


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--backup", required=True, type=Path)
    args = parser.parse_args()
    backup = args.backup.resolve(strict=True)
    checksum = Path(str(backup) + ".sha256")
    if backup.suffix != ".dump" or not backup.stat().st_size or not checksum.is_file():
        raise SystemExit("BACKUP_INVALID; migration not started")
    expected = checksum.read_text(encoding="ascii").split()[0].lower()
    digest = hashlib.sha256()
    with backup.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    if expected != digest.hexdigest():
        raise SystemExit("BACKUP_CHECKSUM_FAILED; migration not started")
    load_environment_file(ROOT / ".env")
    config = Config(str(ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(ROOT / "alembic"))
    command.upgrade(config, "20261003_0010")
    print("TRIAL_SCHEMA_READY; bootstrap owner before restarting public backend")


if __name__ == "__main__":
    main()
