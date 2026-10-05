"""Google-authenticated loopback trial: separate PostgreSQL schema, mock data only."""
import argparse
import json
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
    parser.add_argument("--upgrade-national-scope", action="store_true")
    parser.add_argument("--source-wallet", action="store_true")
    parser.add_argument("--activate-invited-trials-once", action="store_true",
                        help="Apply approved 100 Credit trial policy to previously admitted local invite accounts only")
    parser.add_argument("--expiry-rehearsal", choices=("agency", "province"),
                        help="Use a separate expiry rehearsal schema; original Google trial stays unchanged")
    parser.add_argument("--prepare-expiry-rehearsal", action="store_true")
    parser.add_argument("--run-subscription-maintenance-once", action="store_true",
                        help="Process approved cycles in the isolated local wallet; no worker or payment")
    parser.add_argument("--seed-source-wallets", action="store_true",
                        help="Opt in active Google trial accounts; grant simulated 100 subscription + 600 purchased Credit once")
    parser.add_argument("--mock-outcome", choices=("success", "failure"), default="success")
    args = parser.parse_args()
    if args.activate_invited_trials_once and (not args.source_wallet or any((args.check,
            args.expiry_rehearsal,args.seed_source_wallets,args.run_mock_worker_once,
            args.run_subscription_maintenance_once,args.create_owner_invite,
            args.bootstrap_owner,args.upgrade_national_scope))):
        parser.error("Invited trial activation requires --source-wallet and no other actions")
    if args.prepare_expiry_rehearsal and not args.expiry_rehearsal:
        parser.error("--prepare-expiry-rehearsal requires --expiry-rehearsal")
    if args.expiry_rehearsal and (not args.source_wallet or any((args.seed_source_wallets,
            args.create_owner_invite, args.bootstrap_owner, args.upgrade_national_scope))):
        parser.error("Expiry rehearsal requires --source-wallet and cannot modify original trial accounts")
    if args.prepare_expiry_rehearsal and any((args.check, args.run_mock_worker_once,
                                            args.run_subscription_maintenance_once)):
        parser.error("Prepare rehearsal cannot combine with other actions")
    if args.seed_source_wallets and not args.source_wallet:
        parser.error("--seed-source-wallets requires --source-wallet")
    if args.run_subscription_maintenance_once and (not args.source_wallet or any((
            args.check, args.seed_source_wallets, args.run_mock_worker_once,
            args.create_owner_invite, args.bootstrap_owner, args.upgrade_national_scope))):
        parser.error("Maintenance requires --source-wallet and cannot combine with other actions")
    if args.mock_outcome == "failure" and not args.run_mock_worker_once:
        parser.error("--mock-outcome failure requires --run-mock-worker-once")
    try:
        schema = f"credit_expiry_{args.expiry_rehearsal}" if args.expiry_rehearsal else SCHEMA
        url = isolated_url(ROOT / ".env").update_query_dict({"options": f"-c search_path={schema}", "connect_timeout": "5"})
        auth = read_config(ROOT / ".env.public")
        settings = Settings(database_url=url.render_as_string(hide_password=False), public_read_only=True,
            require_login=True, invite_required=True, shared_registration_enabled=args.source_wallet, paid_requests_enabled=True, formality_credit_cost=5 if args.source_wallet else 3,
            trial_credits_enabled=True, trial_credit_management=True, local_google_trial=True,
            source_wallet_trial=args.source_wallet,
            google_client_id=auth["QD766_GOOGLE_CLIENT_ID"], google_client_secret=auth["QD766_GOOGLE_CLIENT_SECRET"],
            google_redirect_uri="http://127.0.0.1:8771/api/v1/auth/google/callback")
        app = create_app(settings, web_root=ROOT / ".tmp-credit-trial" / "site")
        app.state.collection_probe_checkpoint=ROOT/'.tmp-release-preflight'/'controlled-20261005'/'crawl_state.sqlite'
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
                db.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{schema}"'))
        finally:
            provision.dispose()
        Base.metadata.create_all(app.state.engine)
        if args.activate_invited_trials_once:
            from qd766.backend.invited_trial import activate_invited_trial
            activated=0
            with app.state.session_factory.begin() as db:
                invitations=list(db.scalars(select(TrialInvitation).join(UserAccount,
                    TrialInvitation.used_by==UserAccount.id).where(UserAccount.active.is_(True),
                    UserAccount.trial_admitted.is_(True),UserAccount.root_department_id.is_not(None),
                    UserAccount.external_subject.like("google:%"))))
                for invitation in invitations:
                    activated+=int(activate_invited_trial(db,invitation.used_by,invitation,
                        now=datetime.now(timezone.utc),backfill=True))
            print(f"INVITED_TRIALS_ACTIVATED={activated} CREDIT_PER_TRIAL=100 LOCAL_ONLY LEGACY_BALANCES_UNCHANGED")
            app.state.engine.dispose()
            return 0
        if args.expiry_rehearsal:
            if args.prepare_expiry_rehearsal:
                from sqlalchemy.orm import Session
                from qd766.backend.local_expiry_rehearsal import seed_expiry_rehearsal
                original_url = url.update_query_dict({"options": f"-c search_path={SCHEMA}"})
                original_engine = create_engine(original_url)
                try:
                    with Session(original_engine) as db:
                        owner = db.scalar(select(UserAccount).where(UserAccount.email == OWNER,
                            UserAccount.external_subject.like("google:%"), UserAccount.active.is_(True),
                            UserAccount.trial_admitted.is_(True)))
                        if owner is None:
                            raise ValueError("Verified local owner must exist before rehearsal")
                        identity = {"subject": owner.external_subject, "email": owner.email}
                    with app.state.session_factory.begin() as db:
                        created = seed_expiry_rehearsal(db, owner=identity, tier=args.expiry_rehearsal,
                                                      now=datetime.now(timezone.utc))
                finally:
                    original_engine.dispose()
                print(f"EXPIRY_REHEARSAL_READY TIER={args.expiry_rehearsal} CREATED={created} ORIGINAL_TRIAL_UNCHANGED")
                app.state.engine.dispose()
                return 0
            with app.state.session_factory() as db:
                if db.scalar(select(UserAccount.id)) is None:
                    raise ValueError("Prepare expiry rehearsal before starting it")
        if args.run_subscription_maintenance_once:
            from qd766.backend.subscription_maintenance import run_subscription_maintenance
            result = run_subscription_maintenance(app.state.session_factory,
                                                 now=datetime.now(timezone.utc))
            print(json.dumps({"state": "partial-failure" if result["failures"] else "succeeded",
                              "localOnly": True, **result}))
            app.state.engine.dispose()
            return 1 if result["failures"] else 0
        if args.seed_source_wallets:
            from qd766.backend.wallet_access import enroll
            from qd766.backend.credit_wallet import grant
            from qd766.backend.subscriptions import schedule_plan,grant_due_cycles
            from qd766.backend.models import SubscriptionCycle
            now=datetime.now(timezone.utc)
            with app.state.session_factory.begin() as db:
                accounts=list(db.scalars(select(UserAccount).where(UserAccount.active.is_(True),
                    UserAccount.trial_admitted.is_(True),UserAccount.external_subject.like("google:%"))))
                for account in accounts:
                    enroll(db,account.id,now=now)
                    if db.scalar(select(SubscriptionCycle.id).where(SubscriptionCycle.account_id==account.id,
                            SubscriptionCycle.operation_key=="plan:local-wallet-test-v1:0")) is None:
                        schedule_plan(db,account.id,tier="agency" if account.access_tier=="agency" else "province",
                            origin="trial",operation_key="local-wallet-test-v1",starts_at=now,months=1,now=now)
                    grant_due_cycles(db,account.id,now=now)
                    grant(db,account.id,600,source="purchased",operation_key="local-test-purchased-v1",now=now)
            print(f"SOURCE_WALLET_TEST_ACCOUNTS={len(accounts)} LEGACY_BALANCES_UNCHANGED NO_PRODUCTION_DB")
            app.state.engine.dispose()
            return 0
        if args.upgrade_national_scope:
            with app.state.engine.begin() as db:
                for table,name in (("user_accounts","ck_account_access_tier"),("trial_invitations","ck_invite_tier")):
                    db.execute(text(f'ALTER TABLE "{SCHEMA}"."{table}" DROP CONSTRAINT "{name}"'))
                    db.execute(text(f'ALTER TABLE "{SCHEMA}"."{table}" ADD CONSTRAINT "{name}" CHECK (access_tier IN (\'province\', \'agency\', \'national\'))'))
            print("LOCAL_NATIONAL_SCOPE_READY; only credit_google_trial schema")
            app.state.engine.dispose()
            return 0
        with app.state.session_factory.begin() as db:
            store_normalized_snapshot(db, mock_snapshot())
            bootstrap = db.get(UserAccount, identifier("google-trial:bootstrap"))
            if bootstrap is None and not args.expiry_rehearsal:
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
            def process_mock(job, request):
                if args.mock_outcome == "failure":
                    raise RuntimeError("Local simulated collection failure; no external request")
                return mock_snapshot(request)
            result = run_one_job(app.state.session_factory, process_mock,
                                 worker_id="local-google-mock-worker",
                                 max_attempts=1 if args.mock_outcome == "failure" else 3)
            print(f"MOCK_WORKER_STATE={result.state if result else 'idle'} NO_DVCQG_CALLS")
        if args.create_owner_invite or args.bootstrap_owner or args.run_mock_worker_once:
            app.state.engine.dispose()
            return 0
        print("LOCAL_GOOGLE_TRIAL=http://127.0.0.1:8771/ DATA=SIMULATED CREDIT=TEST ONLY", flush=True)
        if args.expiry_rehearsal:
            print(f"EXPIRY_REHEARSAL={args.expiry_rehearsal} ORIGINAL_TRIAL_UNCHANGED", flush=True)
        print("No worker started; no DVCQG calls. Do not expose this port through a tunnel.", flush=True)
        import uvicorn
        uvicorn.run(app, host="127.0.0.1", port=8771, proxy_headers=False, access_log=False)
        return 0
    except Exception as error:
        print(f"LOCAL_GOOGLE_TRIAL=BLOCKED TYPE={type(error).__name__}; no production fallback.")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
