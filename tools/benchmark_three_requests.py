"""Isolated 18-request probe, while the production queue remains manually paused."""
from __future__ import annotations
import json
import os
import sqlite3
import statistics
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

import httpx
from sqlalchemy import select

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from qd766.backend.config import Settings, load_environment_file
from qd766.backend.database import create_database_engine, create_session_factory
from qd766.backend.jobs import release_collection_lease
from qd766.backend.models import CollectionControl
from qd766.collection import plan_evaluation_requests, _validate_response, TransportResponse
from qd766.normalization import METRIC_GROUPS
from qd766.periods import PeriodSelection

ROOT_ID = '019d2be3-6a88-732b-8b17-b68020c8553a'
UNIT_ID = '019d2be3-6a88-732b-8b18-06f140bf9756'

def main():
    sys.stdout.reconfigure(encoding='utf-8')
    load_environment_file(ROOT / '.env')
    engine = create_database_engine(Settings.from_env())
    factory = create_session_factory(engine)
    owner = f'isolated-three-request-benchmark:{os.getpid()}'
    output = ROOT / '.tmp-release-preflight' / ('benchmark-three-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'))
    stop = threading.Event()
    records = []
    acquired = False
    try:
        with factory.begin() as session:
            control = session.scalar(select(CollectionControl).where(CollectionControl.key == 'dvcqg').with_for_update())
            if control is None or control.circuit_state != 'open' or control.reason != 'operator-requested-pause':
                raise RuntimeError('Requires explicit operator pause; never bypass a source rejection')
            if control.lease_locked_by is not None:
                raise RuntimeError('Another collector holds the lease; no request sent')
            control.lease_locked_by = owner
            control.lease_locked_at = datetime.now(timezone.utc)
        acquired = True
        output.mkdir(parents=True, exist_ok=False)
        checkpoint = sqlite3.connect(output / 'crawl_state.sqlite')
        checkpoint.execute('CREATE TABLE results (month INTEGER, group_name TEXT, state TEXT, details TEXT, PRIMARY KEY(month, group_name))')
        active = 0
        peak = 0
        lock = threading.Lock()
        started = time.perf_counter()
        limits = httpx.Limits(max_connections=3, max_keepalive_connections=3)
        with httpx.Client(timeout=httpx.Timeout(30, connect=10), limits=limits,
                          headers={'Accept':'application/json', 'User-Agent':'qd766-research/1.0 (+controlled benchmark)'}) as client:
            def fetch(month, request):
                nonlocal active, peak
                if stop.is_set():
                    return {'month':month,'group':request.group,'state':'SKIPPED'}
                begin = time.perf_counter()
                with lock:
                    active += 1
                    peak = max(peak,active)
                result = {'month':month,'group':request.group,'state':'FAILED'}
                try:
                    for attempt in range(3):
                        if stop.is_set():
                            result['state']='SKIPPED'
                            break
                        with factory() as session:
                            control=session.get(CollectionControl,'dvcqg')
                            if (control.circuit_state != 'open' or control.reason != 'operator-requested-pause'
                                    or control.lease_locked_by != owner):
                                stop.set()
                                result['error']='control-changed'
                                break
                        result['attempts']=attempt+1
                        try:
                            response=client.post(request.url,json=request.payload)
                        except (httpx.TimeoutException,httpx.TransportError) as exc:
                            result['error']=type(exc).__name__
                            if attempt < 2:
                                stop.wait(2 ** attempt)
                                continue
                            break
                        result['httpStatus']=response.status_code
                        if response.status_code in (401,403,429) or 'text/html' in response.headers.get('content-type','').lower():
                            stop.set()
                            result['error']='source-stop-signal'
                            break
                        if response.status_code >= 500 and attempt < 2:
                            stop.wait(2 ** attempt)
                            continue
                        if response.status_code not in (200,201):
                            result['error']='unexpected-http-status'
                            break
                        envelope=_validate_response(request,TransportResponse(response.status_code,response.content,response.headers.get('content-type')))
                        data=envelope['data']
                        children=data['evaluation' if request.group in METRIC_GROUPS else 'children']
                        pagination=data.get('pagination') or {}
                        if pagination.get('totalPages',1) != 1:
                            result['error']='multiple-pages-not-supported-by-this-probe'
                            break
                        (output / f'month-{month:02d}-{request.group}.json').write_bytes(response.content)
                        unit=next((row for row in children if row['departmentId']==UNIT_ID),None)
                        result.update(state='SUCCESS',rows=len(children)+1,bytes=len(response.content),
                            unitScore=unit.get('totalScore',unit.get('score')) if unit else None)
                        break
                except Exception as exc:
                    result['error']=type(exc).__name__
                finally:
                    result['seconds']=round(time.perf_counter()-begin,4)
                    with lock:
                        active -= 1
                return result

            with ThreadPoolExecutor(max_workers=3) as pool:
                for month in (6,8,9):
                    if stop.is_set():
                        break
                    requests=plan_evaluation_requests(PeriodSelection('month',2026,month),ROOT_ID)
                    for offset in range(0,len(requests),3):
                        futures=[]
                        for request in requests[offset:offset+3]:
                            if stop.is_set():
                                break
                            futures.append(pool.submit(fetch,month,request))
                            stop.wait(0.4)
                        for future in as_completed(futures):
                            item=future.result()
                            records.append(item)
                            checkpoint.execute('INSERT OR REPLACE INTO results VALUES (?,?,?,?)',
                                (item['month'],item['group'],item['state'],json.dumps(item)))
                            checkpoint.commit()
                            print(json.dumps(item),flush=True)
                        if stop.wait(0.4):
                            break
                    if month != 9 and stop.wait(2.5):
                        break
        elapsed=time.perf_counter()-started
        checkpoint.close()
        successes=[r for r in records if r['state']=='SUCCESS']
        totals={str(month):round(sum(r['unitScore'] for r in successes if r['month']==month),2)
            for month in (6,8,9) if len([r for r in successes if r['month']==month and r['unitScore'] is not None])==6}
        report={'expectedRequests':18,'successfulRequests':len(successes),'stoppedOnSignal':stop.is_set(),
            'maxWorkers':3,'peakInFlight':peak,'elapsedSeconds':round(elapsed,3),
            'rows':sum(r['rows'] for r in successes),'bytes':sum(r['bytes'] for r in successes),
            'medianRequestSeconds':statistics.median([r['seconds'] for r in successes]) if successes else None,
            'unitTotals':totals,'productionSnapshotsChanged':False,'records':records}
        (output / 'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
        print(json.dumps({k:v for k,v in report.items() if k!='records'}),flush=True)
        print('REPORT='+str(output / 'report.json'))
    finally:
        if acquired:
            with factory.begin() as session:
                release_collection_lease(session,owner)
        engine.dispose()

if __name__=='__main__':
    main()
