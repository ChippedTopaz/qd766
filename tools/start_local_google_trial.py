"""Google-authenticated loopback trial: separate PostgreSQL schema, mock data only."""
import argparse
from datetime import datetime, timedelta, timezone
from pathlib import Path
import secrets
import sys
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from sqlalchemy import create_engine, select, text
from test_postgresql_credits import isolated_url
from qd766.backend.app import create_app
from qd766.backend.auth import digest
from qd766.backend.config import Settings
from qd766.backend.public_deployment import read_config
from qd766.backend.models import Base, TrialInvitation, UserAccount
from qd766.backend.importer import store_normalized_snapshot
from qd766.backend.local_credit_trial import ROOT as PROVINCE, identifier, mock_catalog, mock_snapshot

OWNER = "vietnt89@gmail.com"
SCHEMA = "credit_google_trial"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--create-owner-invite", action="store_true")
    parser.add_argument("--bootstrap-owner", action="store_true")
    parser.add_argument("--run-mock-worker-once", action="store_true")
    args = parser.parse_args()
    try:
        url = isolated_url(ROOT / ".env").update_query_dict({"options": f"-c search_path={SCHEMA}", "connect_timeout": "5"})
        auth = read_config(ROOT / ".env.public")
        settings = Settings(database_url=url.render_as_string(hide_password=False), public_read_only=True,
            require_login=True, invite_required=True, paid_requests_enabled=True, formality_credit_cost=3,
            trial_credits_enabled=True, trial_credit_management=True, local_google_trial=True,
            google_client_id=auth["QD766_GOOGLE_CLIENT_ID"], google_client_secret=auth["QD766_GOOGLE_CLIENT_SECRET"],
            google_redirect_uri="http://127.0.0.1:8771/api/v1/auth/google/callback")
        app = create_app(settings, web_root=ROOT / ".tmp-credit-trial" / "site")
        class Catalog:
            def load(self, *args, **kwargs):
                return mock_catalog()
        app.state.province_catalog_client = Catalog()
        if args.check:
            app.state.engine.dispose()
            print("LOCAL_GOOGLE_CONFIG=PASS CALLBACK=http://127.0.0.1:8771/api/v1/auth/google/callback")
            print("Google callback registration and real login are not verified.")
            return 0
        provision = create_engine(url)
        try:
            with provision.begin() as db:
                db.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{SCHEMA}"'))
        finally:
            provision.dispose()
        Base.metadata.create_all(app.state.engine)
        with app.state.session_factory.begin() as db:
            store_normalized_snapshot(db, mock_snapshot())
            bootstrap = db.get(UserAccount, identifier("google-trial:bootstrap"))
            if bootstrap is None:
                bootstrap = UserAccount(id=identifier("google-trial:bootstrap"),
                    external_subject="local-trial:bootstrap-no-login", display_name="Local invitation bootstrap",
                    role="admin", active=False, trial_admitted=True, root_department_id=PROVINCE)
                db.add(bootstrap); db.flush()
            if args.create_owner_invite:
                token = secrets.token_urlsafe(32)
                db.add(TrialInvitation(token_hash=digest(token), recipient_email=OWNER,
                    created_by=bootstrap.id, root_department_id=PROVINCE, access_tier="province",
                    expires_at=datetime.now(timezone.utc)+timedelta(days=1)))
            if args.bootstrap_owner:
                owner = db.scalar(select(UserAccount).where(UserAccount.email == OWNER,
                    UserAccount.external_subject.like("google:%"), UserAccount.trial_admitted.is_(True)))
                if owner is None:
                    raise ValueError("Owner must first redeem the local invitation through Google")
                owner.role = "admin"
        if args.create_owner_invite:
            print(f"OWNER_INVITE=http://127.0.0.1:8771/#invite={token}")
            print("Private one-use link for owner only; local database, expires in 1 day.")
        if args.bootstrap_owner:
            print("LOCAL_OWNER_ADMIN_READY; log out and log in again. No credits granted.")
        if args.run_mock_worker_once:
            from qd766.backend.worker import run_one_job
            result = run_one_job(app.state.session_factory, lambda job, request: mock_snapshot(request),
                                 worker_id="local-google-mock-worker")
            print(f"MOCK_WORKER_STATE={result.state if result else 'idle'} NO_DVCQG_CALLS")
        if args.create_owner_invite or args.bootstrap_owner or args.run_mock_worker_once:
            app.state.engine.dispose()
            return 0
        print("LOCAL_GOOGLE_TRIAL=http://127.0.0.1:8771/ DATA=SIMULATED CREDIT=TEST ONLY", flush=True)
        print("No worker started; no DVCQG calls. Do not expose this port through a tunnel.", flush=True)
        import uvicorn
        uvicorn.run(app, host="127.0.0.1", port=8771, proxy_headers=False, access_log=False)
        return 0
    except Exception as error:
        print(f"LOCAL_GOOGLE_TRIAL=BLOCKED TYPE={type(error).__name__}; no production fallback.")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
