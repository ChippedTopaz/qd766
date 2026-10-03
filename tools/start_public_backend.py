"""Run the separate Google-protected backend; no migrations, worker or DNS changes."""
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from qd766.backend.public_deployment import read_config, public_settings, PUBLIC_PORT


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Validate configuration/dependencies without starting or connecting to DB")
    args = parser.parse_args()
    try:
        settings = public_settings(read_config(ROOT / ".env"), read_config(ROOT / ".env.public"))
        from google.oauth2.id_token import verify_oauth2_token  # noqa: F401
        import requests  # noqa: F401
        import uvicorn
        from qd766.backend.app import create_app
        app = create_app(settings)
    except Exception:
        # No exception body: a bad connection URL/configuration can contain secrets.
        print("PUBLIC_BACKEND=BLOCKED: check .env.public, office DB configuration and auth dependencies. No server started.", file=sys.stderr)
        return 1
    if args.check:
        app.state.engine.dispose()
        print("PUBLIC_CONFIG=PASS LOGIN_REQUIRED=True ADMIN_API_BLOCKED=True PAID_REQUESTS=False")
        print("Database connectivity and real Google login are NOT verified by this check.")
        return 0
    print(f"PUBLIC_BACKEND_LOCAL=http://127.0.0.1:{PUBLIC_PORT} LOGIN_REQUIRED=True", flush=True)
    # Tunnel is the only loopback proxy; never trust proxy headers from all hosts.
    uvicorn.run(app, host="127.0.0.1", port=PUBLIC_PORT, access_log=False,
                proxy_headers=True, forwarded_allow_ips="127.0.0.1")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
