"""06:00 Vietnam draft audit. Dry-run by default, sequential shared-lease source reads."""
import argparse,json,os,socket,sqlite3,sys,time,uuid
from contextlib import closing
from pathlib import Path
from datetime import datetime,timezone,timedelta
from sqlalchemy import select,text
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from qd766.backend.config import Settings,load_environment_file
from qd766.backend.database import create_database_engine,create_session_factory
from qd766.backend.models import SourceMonitorRun,SourceMonitorSample,CollectionControl,NationalSummarySnapshot
from qd766.backend.source_monitor import ready,closed_month_baselines,record_month_sample,alert,observe_profile,national_profile
from qd766.backend.province_refresh import VIETNAM
from qd766.backend.jobs import acquire_collection_lease,release_collection_lease,open_collection_circuit
from qd766.periods import PeriodSelection
from qd766.national_summary import collect_national_summary
from qd766.concurrent_collection import PooledHttpTransport
from qd766.collection import SafetyStop

def morning_state(root,now):
    day=now.astimezone(VIETNAM).date()-timedelta(days=1)
    path=Path(root)/'data'/'daily-collection'/str(day)/'crawl_state.sqlite'
    if not path.exists():return 'NOT_STARTED'
    try:
        with closing(sqlite3.connect(path.resolve().as_uri()+'?mode=ro',uri=True,timeout=2)) as checkpoint:
            row=checkpoint.execute("SELECT state,details FROM blocks WHERE block_key='run-status'").fetchone()
        if not row:return 'NOT_STARTED'
        details=json.loads(row[1])
        if row[0]=='COMPLETE' and details.get('completed')==details.get('expected')==102:return 'COMPLETE'
        return row[0] if row[0] in {'RUNNING','INCOMPLETE','HALTED'} else 'INCOMPLETE'
    except (sqlite3.Error,OSError,ValueError):return 'UNAVAILABLE'

def save_run(factory,day,state,details):
    with factory.begin() as db:
        item=db.get(SourceMonitorRun,day)
        if item is None:item=SourceMonitorRun(day=day);db.add(item)
        item.state=state;item.details=details;item.updated_at=datetime.now(timezone.utc)

def execute(factory,**options):
    engine=factory.kw['bind']
    if engine.dialect.name!='postgresql':return _execute(factory,**options)
    # Dedicated session lock also prevents a manual CLI run duplicating the task.
    with engine.connect() as connection:
        held=connection.scalar(text('SELECT pg_try_advisory_lock(7660028)'));connection.commit()
        if not held:return {'state':'busy','reason':'monitor-already-running'}
        try:return _execute(factory,**options)
        finally:connection.execute(text('SELECT pg_advisory_unlock(7660028)'));connection.commit()

def _execute(factory,*,root=ROOT,now=None,read_capture=collect_national_summary,transport_factory=PooledHttpTransport,sleeper=time.sleep):
    fixed_now=now
    now=now or datetime.now(timezone.utc);local=now.astimezone(VIETNAM);day=local.date()
    if local.hour<6:raise ValueError('06:00 guard: no source request before scheduled time')
    with factory() as db:
        if not ready(db):raise ValueError('Monitor schema 0028 is not ready')
        old=db.get(SourceMonitorRun,day)
        if old and old.state=='complete':return {'state':'complete','resumed':True}
        completed=list(old.details.get('completed',[])) if old else []
    details={'completed':completed,'expected':0,'failed':[],'scheduledAt':'06:00 Asia/Ho_Chi_Minh'}
    wait_deadline=time.monotonic()+max(0,(local.replace(hour=9,minute=0,second=0,microsecond=0)-local).total_seconds())
    while True:
        status=morning_state(root,fixed_now or datetime.now(timezone.utc))
        if status=='COMPLETE':break
        if status!='RUNNING' or time.monotonic()>=wait_deadline:
            details['reason']='morning-'+status.lower();save_run(factory,day,'not-checked',details)
            with factory.begin() as db:alert(db,'check-failed','Chưa kiểm tra nguồn dữ liệu lúc 06:00',[str(day),'morning'],details)
            return {'state':'not-checked',**details}
        save_run(factory,day,'waiting',details);sleeper(30)
    with factory() as db:
        baselines=[(row.id,row.year,row.period_value) for row in closed_month_baselines(db,now)]
    details['expected']=len(baselines);save_run(factory,day,'running',details)
    owner=f'source-monitor:{socket.gethostname()}:{os.getpid()}';deadline=time.monotonic()+1200
    def release():
        with factory.begin() as db:
            control=db.get(CollectionControl,'dvcqg')
            if control and control.lease_locked_by==owner:release_collection_lease(db,owner)
    def guard():
        with factory() as db:
            control=db.get(CollectionControl,'dvcqg')
            if not control or control.circuit_state!='closed' or control.lease_locked_by!=owner:raise SafetyStop('Source lease unavailable')
    transport=None
    try:
        transport=transport_factory(max_workers=1,spacing=1,guard=guard)
        for identifier,year,month in baselines:
            key=f'month-{year}-{month:02d}'
            if key in completed:continue
            if time.monotonic()>deadline or len(completed)>=120:
                details['reason']='run-budget-exhausted';break
            # Yield to existing user work; never reclaim a worker's fresh lease.
            lease_deadline=min(deadline,time.monotonic()+300)
            while True:
                with factory.begin() as db:
                    if db.get(CollectionControl,'dvcqg') is None:raise SafetyStop('Source control missing')
                    state=acquire_collection_lease(db,owner,lease_seconds=900)
                if state=='acquired':break
                if state=='circuit-open':raise SafetyStop('Source safety pause')
                if time.monotonic()>=lease_deadline:
                    details['reason']='collector-busy';save_run(factory,day,'not-checked',details)
                    with factory.begin() as db:alert(db,'check-failed','Đối chiếu chưa chạy: bộ cào đang bận',[str(day),'busy'],details)
                    return {'state':'not-checked',**details}
                sleeper(5)
            try:
                period=PeriodSelection('month',year,month)
                def watch(data):
                    with factory.begin() as db:
                        observe_profile(db,f'national:month:closed:{year}:{month}',national_profile(data),
                            {'rootId':'national','rootName':'Cả nước','periodType':'month','year':year,'value':month,'group':'national','checkDate':str(day)},
                            seed=national_profile(db.get(NationalSummarySnapshot,identifier).response_data))
                capture=read_capture(period,transport,on_data=watch)
                with factory.begin() as db:
                    baseline=db.get(NationalSummarySnapshot,identifier)
                    changed=record_month_sample(db,baseline,capture,now=capture.captured_at)
                if changed:
                    folder=Path(root)/'data'/'source-monitor'/str(day);folder.mkdir(parents=True,exist_ok=True)
                    with (folder/(key+'-'+uuid.uuid4().hex+'.json')).open('x',encoding='utf-8') as evidence:
                        json.dump({'sourceHash':capture.raw_sha256,'capturedAt':capture.captured_at.isoformat(),'data':capture.response_data},evidence,ensure_ascii=False)
                completed.append(key);details['completed']=list(completed);save_run(factory,day,'running',details)
            except SafetyStop:
                # Preserve provider rejection before the inner finally releases
                # our lease; do not reopen/throttle-bypass on the next process.
                with factory.begin() as db:
                    control=db.get(CollectionControl,'dvcqg')
                    if control and control.circuit_state=='closed' and control.lease_locked_by==owner:
                        open_collection_circuit(db,reason='source-monitor-source-stop',detail={'checkDay':str(day)})
                raise
            except Exception as exc:
                details['failed'].append({'period':key,'error':type(exc).__name__})
            finally:release()
            sleeper(2)
        state='complete' if len(completed)==len(baselines) and not details['failed'] else 'incomplete'
        save_run(factory,day,state,details)
        if state!='complete':
            with factory.begin() as db:alert(db,'check-failed','Đối chiếu kỳ tháng chưa hoàn tất',[str(day),'incomplete'],details)
        return {'state':state,**details}
    except SafetyStop:
        details['reason']='source-safety-paused';save_run(factory,day,'paused',details)
        with factory.begin() as db:
            control=db.get(CollectionControl,'dvcqg')
            if control and control.circuit_state=='closed' and control.lease_locked_by==owner:
                open_collection_circuit(db,reason='source-monitor-source-stop',detail={'checkDay':str(day)})
            alert(db,'check-failed','Đối chiếu tạm dừng an toàn',[str(day),'paused'],details)
        return {'state':'paused',**details}
    except Exception as exc:
        details['reason']='monitor-error';details['error']=type(exc).__name__
        save_run(factory,day,'incomplete',details)
        with factory.begin() as db:
            alert(db,'check-failed','Đối chiếu kỳ tháng gặp lỗi',[str(day),'monitor-error'],details)
        return {'state':'incomplete',**details}
    finally:
        release()
        if transport is not None:transport.close()

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--execute',action='store_true');parser.add_argument('--check',action='store_true');args=parser.parse_args()
    if not args.execute and not args.check:
        print('PLAN_ONLY: daily 06:00 Vietnam; wait for 05:00 complete; closed-month drafts only; no source requests');return 0
    load_environment_file(ROOT/'.env');engine=create_database_engine(Settings.from_env());factory=create_session_factory(engine)
    try:
        if args.check:
            with factory() as db:
                if not ready(db):raise RuntimeError('Monitor schema 0028 required')
            print('SOURCE_MONITOR_SCHEMA=PASS');return 0
        result=execute(factory);print(json.dumps(result,ensure_ascii=False),flush=True)
        return 0 if result['state']=='complete' else 2
    finally:engine.dispose()
if __name__=='__main__':raise SystemExit(main())
