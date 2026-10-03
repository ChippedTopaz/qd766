"""Local, explicit bootstrap for the owner's EXISTING verified Google account."""
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from sqlalchemy import delete, select
from qd766.backend.config import Settings, load_environment_file
from qd766.backend.database import create_database_engine, create_session_factory
from qd766.backend.models import AdminAudit, LoginSession, UserAccount

OWNER_EMAIL = "vietnt89@gmail.com"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--confirm", action="store_true", help="Promote exactly one existing verified Google owner identity")
    args = parser.parse_args()
    if (ROOT / ".env").exists():
        load_environment_file(ROOT / ".env")
    engine = create_database_engine(Settings.from_env())
    try:
        with create_session_factory(engine).begin() as db:
            matches = list(db.scalars(select(UserAccount).where(UserAccount.email == OWNER_EMAIL,
                UserAccount.external_subject.like("google:%")).with_for_update()))
            if len(matches) != 1 or not matches[0].active:
                raise SystemExit("OWNER_NOT_UNIQUE_OR_INACTIVE; no changes made")
            owner = matches[0]
            if not args.confirm:
                print(f"OWNER_MATCHED={owner.id}; rerun with --confirm after backup and migration")
                return
            owner.role = "admin"
            owner.trial_admitted = True
            db.execute(delete(LoginSession).where(LoginSession.account_id == owner.id))
            db.add(AdminAudit(actor_id=owner.id, action="admin.local-bootstrap", details={"accountId": str(owner.id)}))
            print(f"ADMIN_READY={owner.id}; owner must log in again; credits unchanged")
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
