"""Review production invitees; activate only explicit IDs with owner audit and replay protection."""
import argparse
import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from qd766.backend.public_deployment import public_settings, read_config
from qd766.backend.database import create_session_factory
from qd766.backend.models import UserAccount
from qd766.backend.trial_backfill import review, apply_selected
from qd766.backend.credit_wallet import balance
from qd766.backend.wallet_runtime import verify_real_wallet_schema
from rehearse_credit_restore import verified_backup


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--account", action="append", type=uuid.UUID, default=[])
    parser.add_argument("--operation", type=uuid.UUID)
    parser.add_argument("--backup", type=Path)
    parser.add_argument("--sha256")
    parser.add_argument("--confirm", action="store_true")
    args = parser.parse_args()
    engine = None
    try:
        settings = public_settings(read_config(ROOT / ".env"), read_config(ROOT / ".env.public"),
                                   real_wallet=True, requests_paused=True)
        from sqlalchemy.engine import make_url
        if make_url(settings.database_url).database != "qd766":
            raise ValueError("Approved production database required")
        engine = create_engine(settings.database_url,
            connect_args={"connect_timeout": 5, "options": "-c search_path=public"})
        verify_real_wallet_schema(create_session_factory(engine))
        if not args.confirm:
            with Session(engine) as db:
                db.execute(text("SET TRANSACTION READ ONLY"))
                db.execute(text("SET LOCAL statement_timeout='15s'"))
                rows = []
                now = datetime.now(timezone.utc)
                for account in db.scalars(select(UserAccount).order_by(UserAccount.id)):
                    row = review(db, account)[0]
                    wallet = balance(db, account.id, now=now)
                    row.update(availableCredit=wallet["available"], reservedCredit=wallet["reserved"])
                    rows.append(row)
            print(json.dumps({"mode": "REVIEW_ONLY", "accounts": rows}, indent=2))
            return 0
        if not args.account or not args.operation or not args.backup or not args.sha256:
            raise ValueError("Explicit accounts, operation and verified backup required")
        verified_backup(args.backup, args.sha256)
        with Session(engine, info={"real_wallet_enabled": True, "source_wallet_enabled": True}) as db:
            with db.begin():
                db.execute(text("SET LOCAL lock_timeout='10s'"))
                db.execute(text("SET LOCAL statement_timeout='30s'"))
                owner = db.scalar(select(UserAccount).where(UserAccount.email == "vietnt89@gmail.com",
                    UserAccount.role == "admin", UserAccount.active.is_(True)))
                if owner is None:
                    raise ValueError("Verified owner required")
                result = apply_selected(db, account_ids=args.account, administrator_id=owner.id,
                    operation_id=args.operation, now=datetime.now(timezone.utc))
        print(json.dumps({"BACKFILL": "COMMITTED", **result, "creditPerNewTrial": 100}))
        print("NO_ROLE_SCOPE_OR_LEGACY_BALANCE_CHANGED NO_SERVICE_OR_NETLIFY_CHANGE")
        return 0
    except Exception as error:
        print("BACKFILL=FAILED TYPE=" + type(error).__name__ + "; no partial batch committed")
        return 1
    finally:
        if engine is not None:
            engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
