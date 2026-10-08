"""05:00 daily collector. Dry-run default; shared lease, three HTTP requests, resumable blocks."""
import argparse
import json
import os
import socket
import sqlite3
import sys
import time
import uuid
from datetime import date,datetime, timezone
from pathlib import Path
from sqlalchemy import select
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from qd766.backend.config import Settings,load_environment_file
from qd766.backend.database import create_database_engine,create_session_factory
from qd766.backend.daily_history import daily_target,validate_daily_snapshot
from qd766.backend.importer import store_normalized_snapshot
from qd766.backend.national_summaries import store_national_summary
from qd766.backend.models import CollectionControl,DailyObservation,Snapshot,NationalSummarySnapshot
from qd766.backend.jobs import acquire_collection_lease,release_collection_lease,open_collection_circuit
from qd766.collection import plan_evaluation_requests,SafetyStop,CollectionError
from qd766.concurrent_collection import PooledHttpTransport,collect_concurrent_snapshot
from qd766.national_summary import collect_national_summary
from qd766.province_roots import load_province_roots
from qd766.snapshot import build_collected_snapshot

def collect_detail_block(plan,period,capture_dir,transport,on_retry,*,sleeper=time.sleep):
    """Retry failed groups only; immutable successful captures survive attempts."""
    for attempt in range(3):
        try:
            return collect_concurrent_snapshot(plan,period=period,output_dir=capture_dir,transport=transport,max_workers=3,max_retries=4)
        except SafetyStop:raise
        except (CollectionError,TimeoutError,ConnectionError):
            if attempt==2:raise
            on_retry(attempt+1);sleeper(2**attempt)

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--execute',action='store_true')
    parser.add_argument('--expected-report-date',type=date.fromisoformat,help='Guard only; never changes the reporting day')
    args=parser.parse_args()
    report_date,boundary,periods=daily_target(datetime.now(timezone.utc))
    if args.expected_report_date and args.expected_report_date!=report_date:
        raise SystemExit('REPORT_DATE_GUARD_FAILED_NO_COLLECTION')
    roots=list(load_province_roots().values())
    if len(roots)!=34:raise RuntimeError('Expected 34 verified provinces')
    print(json.dumps({'event':'daily-plan','reportDate':str(report_date),'captureNotBefore':boundary.isoformat(),
        'periods':[{'type':p.type,'year':p.year,'value':p.value} for p in periods],
        'detailBlocks':102,'detailRequests':612,'nationalRequests':3,'workers':3}),flush=True)
    if not args.execute:return 0
    load_environment_file(ROOT/'.env')
    engine=create_database_engine(Settings.from_env());factory=create_session_factory(engine)
    directory=ROOT/'data'/'daily-collection'/str(report_date)
    directory.mkdir(parents=True,exist_ok=True)
    checkpoint=sqlite3.connect(directory/'crawl_state.sqlite')
    checkpoint.execute('CREATE TABLE IF NOT EXISTS blocks (block_key TEXT PRIMARY KEY,state TEXT,details TEXT)')
    owner=f'daily:{socket.gethostname()}:{os.getpid()}'
    def mark(key,state,details):
        checkpoint.execute('INSERT INTO blocks VALUES (?,?,?) ON CONFLICT(block_key) DO UPDATE SET state=excluded.state,details=excluded.details',
            (key,state,json.dumps(details)));checkpoint.commit()
        print(json.dumps({'block':key,'state':state,**details}),flush=True)
    def lease():
        deadline=time.monotonic()+300
        while True:
            with factory.begin() as db:state=acquire_collection_lease(db,owner,lease_seconds=900)
            if state=='acquired':return
            if state=='circuit-open':raise SafetyStop('Collection paused; no requests sent')
            if time.monotonic()>deadline:raise RuntimeError('Shared collector busy; resume next attempt')
            time.sleep(5)
    def release():
        with factory.begin() as db:
            control=db.get(CollectionControl,'dvcqg')
            if control and control.lease_locked_by==owner:release_collection_lease(db,owner)
    def guard():
        with factory() as db:
            control=db.get(CollectionControl,'dvcqg')
            if not control or control.circuit_state!='closed' or control.lease_locked_by!=owner:
                raise SafetyStop('Collection control changed')
    transport=PooledHttpTransport(max_workers=3,spacing=.4,guard=guard)
    failed=0;completed=0
    try:
        mark('run-status','RUNNING',{'completed':0,'expected':102,'reportDate':str(report_date),'startedAt':datetime.now(timezone.utc).isoformat()})
        for period in periods:
            label=f'{period.type}-{period.year}-{period.value or 0}'
            national_key=f'daily:{report_date}:{label}:national'
            stored=checkpoint.execute('SELECT state,details FROM blocks WHERE block_key=?',(national_key,)).fetchone()
            summary_id=None
            if stored and stored[0]=='SUCCESS':
                candidate=json.loads(stored[1])['snapshotId']
                with factory() as db:
                    saved=db.get(NationalSummarySnapshot,uuid.UUID(candidate))
                    if saved and saved.period_type==period.type and saved.year==period.year and saved.period_value==period.value:
                        summary_id=candidate
            if summary_id is None:
                try:
                    lease();mark(national_key,'RUNNING',{})
                    capture=None
                    for attempt in range(5):
                        try:capture=collect_national_summary(period,transport);break
                        except SafetyStop:raise
                        except Exception:
                            if attempt==4:raise
                            time.sleep(2**attempt)
                    with factory.begin() as db:
                        summary,_=store_national_summary(db,capture,observation_id=national_key)
                        summary_id=str(summary.id)
                    mark(national_key,'SUCCESS',{'snapshotId':summary_id})
                except SafetyStop:raise
                except Exception as exc:
                    mark(national_key,'FAILED',{'error':type(exc).__name__});failed+=34;continue
                finally:release()
            for root in roots:
                key=f'daily:{report_date}:{label}:{root.root_department_id}'
                with factory() as db:existing=db.scalar(select(DailyObservation.id).where(DailyObservation.block_key==key))
                if existing:
                    completed+=1;mark(key,'SUCCESS',{'resumed':True});continue
                try:
                    lease();mark(key,'RUNNING',{'province':root.province_name})
                    capture_dir=directory/'captures'/label/str(root.root_department_id)
                    plan=plan_evaluation_requests(period,str(root.root_department_id))
                    manifest=collect_detail_block(plan,period,capture_dir,transport,
                        lambda attempt:mark(key,'RETRYING',{'province':root.province_name,'retryAttempt':attempt}))
                    captured_at=max(datetime.fromisoformat(c['capturedAt']) for c in manifest['captures'])
                    if any(datetime.fromisoformat(c['capturedAt'])<boundary for c in manifest['captures']):
                        raise ValueError('Cached group predates daily capture boundary')
                    payload=build_collected_snapshot(capture_dir).to_dict()
                    with factory.begin() as db:
                        snapshot=store_normalized_snapshot(db,payload,observation_id=key)
                        snapshot.created_at=captured_at
                        summary=db.get(NationalSummarySnapshot,uuid.UUID(summary_id))
                        coverage=validate_daily_snapshot(snapshot,summary,report_date,boundary,period,root.root_department_id)
                        snapshot.status_detail={**snapshot.status_detail,'dailyAgencyCoverage':coverage}
                        db.add(DailyObservation(block_key=key,report_date=report_date,root_department_id=root.root_department_id,
                            period_type=period.type,year=period.year,period_value=period.value,snapshot_id=snapshot.id,
                            national_summary_id=summary.id,captured_at=captured_at))
                        snapshot_id=str(snapshot.id)
                    completed+=1;mark(key,'SUCCESS',{'province':root.province_name,'snapshotId':snapshot_id,
                        'sourceOmissionGroups':len(coverage['missingByGroup'])})
                except SafetyStop:raise
                except Exception as exc:
                    failed+=1;mark(key,'FAILED',{'province':root.province_name,'error':type(exc).__name__,
                        'reason':'invalid-data-no-blind-retry' if isinstance(exc,ValueError) else 'retries-exhausted-or-local-error'})
                finally:release()
                time.sleep(2.5)
        mark('run-status','COMPLETE' if completed==102 else 'INCOMPLETE',{'completed':completed,'failed':failed,'expected':102,'reportDate':str(report_date)})
        return 0 if completed==102 else 2
    except SafetyStop:
        mark('run-status','HALTED',{'completed':completed,'reportDate':str(report_date),'reason':'source-or-operator-stop'})
        # A source rejection must not be retried by scheduled restart until reviewed.
        with factory.begin() as db:
            control=db.get(CollectionControl,'dvcqg')
            if control and control.circuit_state=='closed':
                open_collection_circuit(db,reason='daily-source-stop',detail={'reportDate':str(report_date)})
        return 2
    finally:
        release();transport.close();checkpoint.close();engine.dispose()

if __name__=='__main__':raise SystemExit(main())
