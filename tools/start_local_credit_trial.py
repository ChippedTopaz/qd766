"""Offline loopback-only credit simulator; never load office/public .env."""
import argparse
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))
from qd766.backend.local_credit_trial import create_local_credit_trial


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port",type=int,default=8770)
    args=parser.parse_args()
    if args.port in {8767,8768,8769} or not 1024 <= args.port <= 65535:
        parser.error("Use a separate local port; 8767/8768/8769 are reserved")
    directory=ROOT/".tmp-credit-trial"
    site=directory/"site"
    if not (site/"dist"/"local-trial.js").is_file():
        parser.error("Build isolated trial assets with start_local_credit_trial.ps1 first")
    directory.mkdir(exist_ok=True)
    app=create_local_credit_trial("sqlite+pysqlite:///"+(directory/"credit-trial.sqlite").as_posix(),site)
    print(f"LOCAL_SIMULATION=http://127.0.0.1:{args.port}/local-trial.html",flush=True)
    print("DATA=SIMULATED PRICE=3_TEST_CREDITS NO_DVCQG_CALLS NO_PRODUCTION_CHANGES",flush=True)
    import uvicorn
    uvicorn.run(app,host="127.0.0.1",port=args.port,access_log=False,proxy_headers=False)


if __name__=="__main__":
    main()
