"""Office-only account assignment. Never promote accounts through a browser request."""
import argparse
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from sqlalchemy import select, delete
from qd766.backend.config import Settings, load_environment_file
from qd766.backend.database import create_database_engine, create_session_factory
from qd766.backend.models import Department, LoginSession, UserAccount
from qd766.province_roots import load_province_roots


def main():
    parser = argparse.ArgumentParser(description="List, assign province or disable QD766 accounts locally")
    parser.add_argument("action", choices=["list", "assign-province", "disable"])
    parser.add_argument("--account-id", type=uuid.UUID)
    parser.add_argument("--province-code")
    args = parser.parse_args()
    if (ROOT / ".env").exists():
        load_environment_file(ROOT / ".env")
    if args.action != "list" and not args.account_id:
        parser.error("--account-id is required")
    engine = create_database_engine(Settings.from_env())
    try:
        with create_session_factory(engine).begin() as db:
            if args.action == "list":
                for account in db.scalars(select(UserAccount).order_by(UserAccount.created_at)):
                    print(f"{account.id} | {account.email or '-'} | {account.plan} | province={account.root_department_id or 'pending'} | active={account.active}")
                return
            account = db.scalar(select(UserAccount).where(UserAccount.id == args.account_id).with_for_update())
            if account is None:
                parser.error("Account does not exist")
            if args.action == "assign-province":
                root = load_province_roots().get(args.province_code or "")
                if root is None or db.get(Department, root.root_department_id) is None:
                    parser.error("Use a verified province code already stored in this database")
                account.root_department_id = root.root_department_id
                account.access_tier = "province"
                account.unit_department_id = None
            else:
                account.active = False
            # Assignment or disable revokes old sessions; user must log in again.
            db.execute(delete(LoginSession).where(LoginSession.account_id == account.id))
            print("ACCOUNT_UPDATED; sessions revoked; plan and credit unchanged")
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
