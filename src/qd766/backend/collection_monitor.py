"""Admin-only, read-only collection monitor. No queue/circuit controls."""
import json
import sqlite3
from pathlib import Path
from collections import Counter
from sqlalchemy import select, func
from .models import CollectionControl, CollectionJob, Department, ProvinceCollectionBatch, PaidDataRequest, UserAccount, Formality

def stamp(value):
    return value.isoformat() if value else None

def daily_status():
    """Trusted server-local checkpoint paths only; read-only, no task execution."""
    root=Path(__file__).resolve().parents[3]/'data'/'daily-collection'
    if not root.is_dir():return []
    reports=[]
    for directory in sorted(root.iterdir(),reverse=True):
        from datetime import date
        try:day=date.fromisoformat(directory.name)
        except ValueError:continue
        path=directory/'crawl_state.sqlite'
        if not path.is_file() or path.resolve().parent.parent!=root.resolve():continue
        try:
            with sqlite3.connect(path.as_uri()+'?mode=ro',uri=True,timeout=2) as db:
                rows=db.execute('SELECT block_key,state,details FROM blocks').fetchall()
            blocks=[(key,state,json.loads(raw)) for key,state,raw in rows if key!='run-status']
            status=next((state for key,state,_ in rows if key=='run-status'),'RUNNING')
            reports.append({'reportDate':str(day),'state':status,'expected':102,
                'completed':sum(state=='SUCCESS' and not key.endswith(':national') for key,state,_ in blocks),
                'failures':[{'block':key,'province':details.get('province'),'error':details.get('error'),'state':state}
                            for key,state,details in blocks if state in ('FAILED','HALTED')],
                'counts':dict(Counter(state for _,state,_ in blocks))})
        except (sqlite3.Error,ValueError):reports.append({'reportDate':str(day),'state':'UNREADABLE','expected':102,'completed':0,'failures':[],'counts':{}})
        if len(reports)>=7:break
    return reports

def collection_status(db, *, kind=None, source=None, state=None, offset=0, limit=30):
    query=select(CollectionJob)
    linked_request=select(PaidDataRequest.id).where(PaidDataRequest.collection_job_id==CollectionJob.id).exists()
    if source=='user':query=query.where(linked_request)
    elif source=='system':query=query.where(~linked_request)
    if state:
        query=query.where(CollectionJob.state==state)
    if kind=='formality':
        query=query.where(CollectionJob.request['scope'].as_string()=='formality')
    elif kind=='default':
        query=query.where(CollectionJob.request['scope'].as_string()=='all')
    total=db.scalar(select(func.count()).select_from(query.subquery()))
    jobs=list(db.scalars(query.order_by(CollectionJob.created_at.desc(),CollectionJob.id.desc()).offset(offset).limit(limit)))
    ids=[]
    import uuid
    for job in jobs:
        try: ids.append(uuid.UUID(job.request.get('rootDepartmentId','')))
        except (ValueError,TypeError,AttributeError): pass
    names={str(d.id):d.name for d in db.scalars(select(Department).where(Department.id.in_(ids)))} if ids else {}
    requested={}
    for job_id,name in db.execute(select(PaidDataRequest.collection_job_id,UserAccount.display_name).join(
            UserAccount,UserAccount.id==PaidDataRequest.account_id).where(PaidDataRequest.collection_job_id.in_([j.id for j in jobs]))):
        requested.setdefault(job_id,set()).add(name)
    formality_ids=[]
    for j in jobs:
        try: formality_ids.append(uuid.UUID(j.request.get('formalityId','')))
        except (ValueError,TypeError,AttributeError): pass
    formalities={str(f.id):f'{f.code} · {f.name}' for f in db.scalars(select(Formality).where(Formality.id.in_(formality_ids)))} if formality_ids else {}
    count_rows=query.subquery()
    counts=dict(db.execute(select(count_rows.c.state,func.count()).group_by(count_rows.c.state)).all())
    control=db.get(CollectionControl,'dvcqg')
    batches=list(db.scalars(select(ProvinceCollectionBatch).order_by(ProvinceCollectionBatch.created_at.desc()).limit(30)))
    return {'counts':counts,'total':total,'offset':offset,'limit':limit,
        'control':{'state':control.circuit_state if control else 'unknown','reason':control.reason if control else None},
        'jobs':[{'id':str(j.id),'state':j.state,'kind':'formality' if j.request.get('scope')=='formality' else 'default',
            'province':names.get(j.request.get('rootDepartmentId'),'Chưa xác định'),
            'period':j.request.get('period',{}),'formalityId':j.request.get('formalityId'),
            'requestedBy':sorted(requested.get(j.id,set())), 'formalityName':formalities.get(j.request.get('formalityId')),
            'attempts':j.attempts,'priority':j.priority,'createdAt':stamp(j.created_at),
            'startedAt':stamp(j.locked_at),'updatedAt':stamp(j.updated_at),'nextRunAt':stamp(j.next_run_at),
            'errorKind':(j.error or {}).get('kind'),'expectedGroups':5 if j.request.get('scope')=='formality' else 6}
            for j in jobs],
        'batches':[{'id':str(b.id),'state':b.state,'period':{'type':b.period_type,'year':b.year,
            b.period_type:b.period_value} if b.period_value else {'type':b.period_type,'year':b.year},
            'total':b.total_items,'completed':b.completed_items,'skipped':b.available_items,
            'failed':b.failed_items,'updatedAt':stamp(b.updated_at)} for b in batches]}

def probe_status(path):
    """Only a server-configured checkpoint path; never take a path from clients."""
    if path is None or not path.is_file():
        return None
    try:
        with sqlite3.connect(path.as_uri()+'?mode=ro',uri=True,timeout=2) as db:
            rows=db.execute('SELECT block_key,state,details FROM blocks').fetchall()
        phases={}
        errors=[]
        for key,state,raw in rows:
            if key=='run-status':
                continue
            phase='national' if key.startswith('national:') else key.split(':')[0]
            counts=phases.setdefault(phase,Counter())
            counts[state]+=1
            if state in ('FAILED','HALTED'):
                info=json.loads(raw)
                errors.append({'phase':phase,'province':info.get('province'),'state':state,'error':info.get('error')})
        status=next((state for key,state,_ in rows if key=='run-status'),'RUNNING')
        return {'label':'Đợt kiểm chứng dữ liệu thật · 05/10/2026','state':status,
            'phases':[{'period':key,'counts':dict(value),'total':5 if key=='national' else 34} for key,value in phases.items()],
            'errors':errors[:30]}
    except (OSError,sqlite3.Error,ValueError):
        return {'label':'Đợt kiểm chứng dữ liệu thật','state':'UNAVAILABLE','phases':[],'errors':[]}
