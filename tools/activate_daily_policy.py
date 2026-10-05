"""Reconcile verified legacy default batches, preserve paid requests, then resume explicitly."""
import argparse,json,sys
from pathlib import Path
from datetime import datetime,timezone
from sqlalchemy import select,func,inspect
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from qd766.backend.config import Settings,load_environment_file
from qd766.backend.database import create_database_engine,create_session_factory
from qd766.backend.models import CollectionControl,CollectionJob,PaidDataRequest,ProvinceCollectionBatch,ProvinceCollectionBatchItem,Snapshot,Dataset
from qd766.backend.jobs import close_collection_circuit
from qd766.province_roots import load_province_roots

def reconcile(db,confirm=False):
    control=db.scalar(select(CollectionControl).where(CollectionControl.key=='dvcqg').with_for_update())
    if control is None or control.circuit_state!='open' or control.reason!='operator-requested-pause' or control.lease_locked_by:
        raise RuntimeError('Requires idle operator-requested pause; no changes')
    roots={root.root_department_id for root in load_province_roots().values()}
    batches=list(db.scalars(select(ProvinceCollectionBatch).where(ProvinceCollectionBatch.state.in_(['queued','running','failed','halted']))))
    verified=[];jobs_to_halt=[]
    for batch in batches:
        rows=db.execute(select(Snapshot.root_department_id,func.count(Dataset.id)).join(Dataset).where(
            Snapshot.scope=='all',Snapshot.state=='complete',Snapshot.period_type==batch.period_type,
            Snapshot.year==batch.year,Snapshot.period_value==batch.period_value,Snapshot.created_at>=batch.created_at,
            Snapshot.root_department_id.in_(roots)).group_by(Snapshot.id,Snapshot.root_department_id)).all()
        if not roots.issubset({root for root,count in rows if count==6}):
            raise RuntimeError(f'Legacy batch {batch.id} lacks newer 34x6 coverage; nothing changed')
        jobs=list(db.scalars(select(CollectionJob).where(CollectionJob.state.in_(['queued','running','failed','halted']),
            CollectionJob.request['provinceBatchId'].as_string()==str(batch.id))))
        for job in jobs:
            if job.request.get('scope')!='all' or db.scalar(select(PaidDataRequest.id).where(PaidDataRequest.collection_job_id==job.id).limit(1)):
                raise RuntimeError('Paid/ambiguous job linked to default batch; nothing changed')
        verified.append(batch);jobs_to_halt.extend(jobs)
    if confirm:
        for batch in verified:
            items=list(db.scalars(select(ProvinceCollectionBatchItem).where(ProvinceCollectionBatchItem.batch_id==batch.id)))
            for item in items:
                if item.state!='succeeded':item.state='skipped';item.error={'kind':'verified-independent-refresh'}
            batch.state='succeeded';batch.completed_items=sum(item.state=='succeeded' for item in items)
            batch.available_items=sum(item.state=='skipped' for item in items);batch.failed_items=0
            batch.error={'kind':'reconciled-independent-refresh','at':datetime.now(timezone.utc).isoformat()}
        for job in jobs_to_halt:
            job.state='halted';job.locked_at=None;job.locked_by=None
            job.error={'kind':'superseded-by-verified-refresh','retryable':False}
        close_collection_circuit(db)
    return {'state':'activated' if confirm else 'planned','verifiedBatches':len(verified),'obsoleteDefaultJobs':len(jobs_to_halt),'paidRequestsUnchanged':True}

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--confirm',action='store_true');args=parser.parse_args()
    load_environment_file(ROOT/'.env');engine=create_database_engine(Settings.from_env());factory=create_session_factory(engine)
    try:
        if args.confirm and not inspect(engine).has_table('daily_observations'):raise RuntimeError('Daily migration required')
        with factory.begin() as db:report=reconcile(db,args.confirm)
        print(json.dumps(report))
    finally:engine.dispose()
if __name__=='__main__':main()
