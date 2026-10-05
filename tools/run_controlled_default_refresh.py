"""Reviewed 3-request refresh of Sep/Oct, Q3/Q4 and year; old queue stays paused."""
from __future__ import annotations
import argparse
import json
import os
import sqlite3
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from sqlalchemy import select

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from qd766.backend.config import Settings, load_environment_file
from qd766.backend.database import create_database_engine, create_session_factory
from qd766.backend.importer import store_normalized_snapshot
from qd766.backend.jobs import release_collection_lease
from qd766.backend.models import CollectionControl
from qd766.backend.national_summaries import store_national_summary
from qd766.collection import plan_evaluation_requests, SafetyStop
from qd766.concurrent_collection import PooledHttpTransport, collect_concurrent_snapshot
from qd766.national_summary import collect_national_summary
from qd766.periods import PeriodSelection
from qd766.province_roots import load_province_roots
from qd766.snapshot import build_collected_snapshot

PERIODS=[PeriodSelection('month',2026,9),PeriodSelection('month',2026,10),
         PeriodSelection('quarter',2026,3),PeriodSelection('quarter',2026,4),PeriodSelection('year',2026)]

def main():
    sys.stdout.reconfigure(encoding='utf-8')
    parser=argparse.ArgumentParser()
    parser.add_argument('--execute',action='store_true')
    parser.add_argument('--run-id',default='controlled-20261005')
    parser.add_argument('--historical-backfill',action='store_true',help='Collect months 1-8 and quarters 1-2 of 2026; August/Ca Mau first')
    args=parser.parse_args()
    if not args.run_id or any(c not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_' for c in args.run_id):
        parser.error('run-id must be a simple directory name')
    roots=list(load_province_roots().values())
    if len(roots)!=34:
        raise RuntimeError('Expected validated 34-province catalog')
    roots.sort(key=lambda r:(str(r.root_department_id)!='019d2be3-6a88-732b-8b17-b68020c8553a',r.province_code))
    periods=PERIODS
    if args.historical_backfill:
        periods=[PeriodSelection('month',2026,m) for m in [8,1,2,3,4,5,6,7]]+[PeriodSelection('quarter',2026,q) for q in [1,2]]
        roots.sort(key=lambda r:(r.province_name!='Cà Mau',r.province_code))
    expected_blocks=len(periods)*(len(roots)+1)
    if not args.execute:
        print(json.dumps({'state':'planned','provincePeriods':len(periods)*len(roots),'minimumDetailRequests':len(periods)*len(roots)*6,
            'nationalRequests':len(periods),'maxWorkers':3,'oldQueueRemainsPaused':True}))
        return 0
    load_environment_file(ROOT/'.env')
    output=ROOT/'.tmp-release-preflight'/args.run_id
    output.mkdir(parents=True,exist_ok=True)
    checkpoint=sqlite3.connect(output/'crawl_state.sqlite')
    checkpoint.execute('CREATE TABLE IF NOT EXISTS blocks (block_key TEXT PRIMARY KEY, state TEXT, details TEXT)')
    engine=create_database_engine(Settings.from_env())
    factory=create_session_factory(engine)
    owner=f'controlled-default-refresh:{os.getpid()}'
    acquired=False
    transport=None
    started=time.monotonic()

    def mark(key,state,details):
        checkpoint.execute('INSERT OR REPLACE INTO blocks VALUES (?,?,?)',(key,state,json.dumps(details,ensure_ascii=False)))
        checkpoint.commit()
        print(json.dumps({'block':key,'state':state,**details},ensure_ascii=False),flush=True)

    def successful(key):
        row=checkpoint.execute('SELECT state FROM blocks WHERE block_key=?',(key,)).fetchone()
        return bool(row and row[0]=='SUCCESS')

    def guard():
        with factory() as session:
            control=session.get(CollectionControl,'dvcqg')
            if (control is None or control.circuit_state!='open' or control.reason!='operator-requested-pause'
                    or control.lease_locked_by!=owner):
                raise SafetyStop('Operator pause/lease changed; stop isolated refresh')

    try:
        with factory.begin() as session:
            control=session.scalar(select(CollectionControl).where(CollectionControl.key=='dvcqg').with_for_update())
            if (control is None or control.circuit_state!='open' or control.reason!='operator-requested-pause'
                    or control.lease_locked_by is not None):
                raise RuntimeError('Requires idle, explicitly operator-paused collector; no queue resumed')
            control.lease_locked_by=owner
            control.lease_locked_at=datetime.now(timezone.utc)
        acquired=True
        transport=PooledHttpTransport(max_workers=3,spacing=0.4,guard=guard)
        for period in periods:
            period.validate_collectable()
            label=f'{period.type}-{period.year}-{period.value or 0}'
            key='national:'+label
            if not successful(key):
                try:
                    capture=collect_national_summary(period,transport)
                    with factory.begin() as session:
                        stored,created=store_national_summary(session,capture)
                    mark(key,'SUCCESS',{'snapshotId':str(stored.id),'created':created,'groups':stored.group_count})
                except SafetyStop:
                    raise
                except Exception as exc:
                    mark(key,'FAILED',{'error':type(exc).__name__,'message':str(exc)[:240]})
        for period in periods:
            label=f'{period.type}-{period.year}-{period.value or 0}'
            for root in roots:
                key=label+':'+str(root.root_department_id)
                if successful(key):
                    continue
                guard()
                with factory.begin() as session:
                    control=session.get(CollectionControl,'dvcqg')
                    control.lease_locked_at=datetime.now(timezone.utc)
                directory=output/'captures'/label/str(root.root_department_id)
                mark(key,'RUNNING',{'province':root.province_name})
                try:
                    plan=plan_evaluation_requests(period,str(root.root_department_id))
                    collect_concurrent_snapshot(plan,period=period,output_dir=directory,
                        transport=transport,max_workers=3,max_retries=4)
                    payload=build_collected_snapshot(directory).to_dict()
                    with factory.begin() as session:
                        snapshot=store_normalized_snapshot(session,payload,observation_id=args.run_id+':'+key)
                        snapshot_id=str(snapshot.id)
                    mark(key,'SUCCESS',{'province':root.province_name,'snapshotId':snapshot_id,
                        'groups':len(payload['datasets']),'validatedAt':datetime.now(timezone.utc).isoformat()})
                except SafetyStop:
                    mark(key,'HALTED',{'province':root.province_name,'error':'source-or-operator-stop'})
                    raise
                except Exception as exc:
                    mark(key,'FAILED',{'province':root.province_name,'error':type(exc).__name__,'message':str(exc)[:240]})
                time.sleep(2.5)
        counts=dict(checkpoint.execute("SELECT state,COUNT(*) FROM blocks WHERE block_key!='run-status' GROUP BY state").fetchall())
        mark('run-status','COMPLETE' if counts.get('SUCCESS')==expected_blocks else 'INCOMPLETE',
            {'counts':counts,'seconds':round(time.monotonic()-started,2),'expectedBlocks':expected_blocks})
    except SafetyStop as exc:
        mark('run-status','HALTED',{'message':str(exc)[:240]})
        with factory.begin() as session:
            control=session.get(CollectionControl,'dvcqg')
            if control.lease_locked_by==owner and control.reason=='operator-requested-pause':
                control.reason='controlled-refresh-safety-stop'
                control.detail={'kind':'requires-review','runId':args.run_id,'message':str(exc)[:240]}
        return 2
    finally:
        if transport:
            transport.close()
        if acquired:
            with factory.begin() as session:
                release_collection_lease(session,owner)
        checkpoint.close()
        engine.dispose()
    return 0

if __name__=='__main__':
    raise SystemExit(main())
