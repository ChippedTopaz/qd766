"""Plan daily open-period refresh + one post-close capture; dry-run by default."""
import argparse
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path
from sqlalchemy import select
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from qd766.backend.config import Settings,load_environment_file
from qd766.backend.database import create_database_engine,create_session_factory
from qd766.backend.models import CollectionControl,ProvinceCollectionBatch,Snapshot
from qd766.backend.province_refresh import daily_refresh_candidates,due_daily_periods,refresh_cutoff,VIETNAM
from qd766.backend.province_batches import create_province_batch
from qd766.province_roots import load_province_roots
from manage_province_batch import _catalog_version

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--confirm',action='store_true',help='Explicitly enqueue; default is SELECT-only plan')
    args=parser.parse_args()
    load_environment_file(ROOT/'.env')
    now=datetime.now(VIETNAM)
    roots=list(load_province_roots().values())
    if len(roots)!=34: raise RuntimeError('Expected 34 validated roots')
    ids={r.root_department_id for r in roots}
    engine=create_database_engine(Settings.from_env())
    factory=create_session_factory(engine)
    try:
        with factory.begin() as db:
            control=db.get(CollectionControl,'dvcqg')
            if args.confirm:
                control=db.scalar(select(CollectionControl).where(CollectionControl.key=='dvcqg').with_for_update())
                if control is None or control.circuit_state!='closed':
                    raise RuntimeError('Circuit is not closed; nothing queued')
                if db.scalar(select(ProvinceCollectionBatch.id).where(ProvinceCollectionBatch.state.in_(['queued','running','failed','halted'])).limit(1)):
                    raise RuntimeError('Existing batches need completion/review; nothing queued')
            latest={}
            for period in daily_refresh_candidates(now):
                rows=db.execute(select(Snapshot.root_department_id,Snapshot.created_at).where(
                    Snapshot.state=='complete',Snapshot.scope=='all',Snapshot.root_department_id.in_(ids),
                    Snapshot.period_type==period.type,Snapshot.year==period.year,Snapshot.period_value==period.value)).all()
                captures={}
                for root,at in rows:
                    if at.tzinfo is None: at=at.replace(tzinfo=VIETNAM)
                    captures[root]=max(at,captures.get(root,at))
                if ids.issubset(captures): latest[(period.type,period.year,period.value)]=min(captures.values())
            periods=due_daily_periods(now,latest)
            output=[]
            for period in periods:
                cutoff=refresh_cutoff(period,now)
                item={'type':period.type,'year':period.year,'value':period.value,'freshAfter':cutoff.isoformat()}
                if args.confirm:
                    batch,created=create_province_batch(db,roots,period,catalog_version=_catalog_version(),
                        refresh_key=f'daily-policy:{now.date().isoformat()}',fresh_after=cutoff-timedelta(microseconds=1))
                    item.update(batchId=str(batch.id),created=created)
                output.append(item)
        print(json.dumps({'state':'queued' if args.confirm else 'planned','policy':'daily-and-finalize',
            'periods':output,'circuit':control.circuit_state if control else None},indent=2))
    finally:
        engine.dispose()

if __name__=='__main__':main()
