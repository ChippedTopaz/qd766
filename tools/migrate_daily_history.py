"""Add daily history only after checking a fresh pg_dump and checksum."""
import argparse,hashlib,sys
from pathlib import Path
from datetime import datetime,timezone,timedelta
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from alembic import command
from alembic.config import Config
from qd766.backend.config import load_environment_file

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--backup',type=Path,required=True);args=parser.parse_args()
    path=args.backup.resolve(strict=True);checksum=Path(str(path)+'.sha256')
    if path.suffix!='.dump' or not path.stat().st_size or not checksum.is_file():raise SystemExit('BACKUP_INVALID')
    if datetime.now(timezone.utc)-datetime.fromtimestamp(path.stat().st_mtime,timezone.utc)>timedelta(hours=24):raise SystemExit('BACKUP_TOO_OLD')
    with path.open('rb') as stream:digest=hashlib.file_digest(stream,'sha256').hexdigest()
    if digest!=checksum.read_text(encoding='ascii').split()[0].lower():raise SystemExit('BACKUP_CHECKSUM_FAILED')
    load_environment_file(ROOT/'.env');config=Config(str(ROOT/'alembic.ini'))
    config.set_main_option('script_location',str(ROOT/'alembic'));command.upgrade(config,'20261005_0017')
    print('DAILY_HISTORY_SCHEMA_READY')
if __name__=='__main__':main()
