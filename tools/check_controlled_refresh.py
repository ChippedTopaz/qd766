"""Read-only SQLite checkpoint status for the isolated controlled refresh."""
import json
import sqlite3
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
path=ROOT/'.tmp-release-preflight'/'controlled-20261005'/'crawl_state.sqlite'
with sqlite3.connect(path.as_uri()+'?mode=ro',uri=True) as db:
    rows=db.execute('SELECT block_key,state,details FROM blocks').fetchall()
periods={}
failures=[]
for key,state,raw in rows:
    if key=='run-status':
        continue
    period='national' if key.startswith('national:') else key.split(':')[0]
    states=periods.setdefault(period,{})
    states[state]=states.get(state,0)+1
    if state in ('FAILED','HALTED'):
        failures.append({'block':key,'state':state,'details':json.loads(raw)})
print(json.dumps({'expectedProvincePeriods':170,'periods':periods,'failures':failures,
    'complete':sum(state=='SUCCESS' for key,state,_ in rows if key!='run-status')==175},ensure_ascii=True,indent=2))
