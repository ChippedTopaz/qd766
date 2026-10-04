"""Run the separate Google-protected backend; no migrations, worker or DNS changes."""
import argparse
import logging
import logging.config
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from qd766.backend.public_deployment import read_config, public_settings, PUBLIC_PORT


def background_log_config():
    directory = ROOT / ".tmp-public-logs"
    directory.mkdir(exist_ok=True)
    return {"version": 1, "disable_existing_loggers": False,
        "formatters": {"safe": {"format": "%(asctime)s %(levelname)s %(message)s"}},
        "handlers": {"file": {"class": "logging.handlers.RotatingFileHandler",
            "filename": str(directory / "public-backend-v2.log"), "encoding": "utf-8",
            "maxBytes": 10 * 1024 * 1024, "backupCount": 5, "formatter": "safe"}},
        "loggers": {"qd766.public": {"handlers": ["file"], "level": "INFO", "propagate": False},
            "uvicorn": {"handlers": ["file"], "level": "INFO", "propagate": False},
            "uvicorn.error": {"level": "INFO"},
            "uvicorn.access": {"handlers": [], "propagate": False}}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="No server start; real-wallet also verifies DB schema read-only")
    parser.add_argument("--background-log", action="store_true", help="Write UTF-8 logs without a console; no request access logging")
    parser.add_argument("--real-wallet",action="store_true",help="Explicit opt-in after approved migration/backfill; never enables payment")
    parser.add_argument("--pause-paid-requests",action="store_true",help="With real-wallet: pause new requests without disabling existing wallet reads/settlement")
    args = parser.parse_args()
    log_config = background_log_config() if args.background_log else None
    if log_config:
        logging.config.dictConfig(log_config)
    def report(message, error=False):
        if args.background_log:
            logger = logging.getLogger("qd766.public")
            (logger.error if error else logger.info)(message)
        else:
            print(message, file=sys.stderr if error else sys.stdout, flush=True)
    try:
        settings = public_settings(read_config(ROOT / ".env"), read_config(ROOT / ".env.public"),
            real_wallet=args.real_wallet,requests_paused=args.pause_paid_requests)
        from google.oauth2.id_token import verify_oauth2_token  # noqa: F401
        import requests  # noqa: F401
        import uvicorn
        from qd766.backend.app import create_app
        app = create_app(settings)
        if settings.real_wallet_enabled:
            from qd766.backend.wallet_runtime import verify_real_wallet_schema
            verify_real_wallet_schema(app.state.session_factory)
    except Exception:
        # No exception body: a bad connection URL/configuration can contain secrets.
        report("PUBLIC_BACKEND=BLOCKED: check .env.public, office DB configuration/schema and auth dependencies. No server started.", error=True)
        return 1
    if args.check:
        app.state.engine.dispose()
        report("PUBLIC_CONFIG=PASS LOGIN_REQUIRED=True INVITE_REQUIRED=True ADMIN_ROLE_REQUIRED=True OPERATOR_API_BLOCKED=True "
            f"PAID_REQUESTS={settings.paid_requests_enabled} REAL_WALLET={settings.real_wallet_enabled} REQUESTS_PAUSED={settings.wallet_requests_paused}")
        report("Wallet schema/connectivity verified read-only." if settings.real_wallet_enabled else "Database connectivity NOT verified.")
        report("Real Google login and DVCQG collection are NOT verified by this check.")
        return 0
    report(f"PUBLIC_BACKEND_LOCAL=http://127.0.0.1:{PUBLIC_PORT} LOGIN_REQUIRED=True")
    # Tunnel is the only loopback proxy; never trust proxy headers from all hosts.
    options = {"log_config": log_config} if log_config else {}
    uvicorn.run(app, host="127.0.0.1", port=PUBLIC_PORT, access_log=False,
                proxy_headers=True, forwarded_allow_ips="127.0.0.1", **options)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
