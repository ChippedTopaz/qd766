"""Admin-only source alerts. Review status never publishes drafts or starts a crawl."""
import uuid
from datetime import datetime,timezone
from typing import Literal
from fastapi import APIRouter,Request,HTTPException,Query
from pydantic import BaseModel,ConfigDict,Field
from sqlalchemy import select,func
from .admin import administrator,audit
from .models import SourceMonitorAlert,SourceMonitorRun,Snapshot
from .source_monitor import ready
from .province_refresh import VIETNAM
router=APIRouter(prefix='/api/v1/admin/source-monitor',tags=['source monitoring'])

def require_schema(db):
    if not ready(db):raise HTTPException(503,'Chưa nâng schema giám sát nguồn dữ liệu.')
def item_payload(item,detail=False):
    data={'id':str(item.id),'kind':item.kind,'title':item.title,'createdAt':item.created_at.isoformat(),
        'updatedAt':item.updated_at.isoformat(),'read':item.read_at is not None,'resolved':item.resolved_at is not None,
        'occurrences':item.occurrences,'changeCount':item.details.get('changeCount',0),'confirmed':item.details.get('confirmed',False)}
    if detail:data['details']=item.details
    return data

@router.get('')
def overview(request:Request,page:int=Query(1,ge=1,le=100000),state:Literal['all','unread','open','resolved']='open'):
    with request.app.state.session_factory() as db:
        administrator(request,db);require_schema(db)
        predicates=[]
        if state=='unread':predicates=[SourceMonitorAlert.read_at.is_(None),SourceMonitorAlert.resolved_at.is_(None)]
        if state=='open':predicates=[SourceMonitorAlert.resolved_at.is_(None)]
        if state=='resolved':predicates=[SourceMonitorAlert.resolved_at.is_not(None)]
        total=db.scalar(select(func.count()).select_from(SourceMonitorAlert).where(*predicates))
        unread=db.scalar(select(func.count()).select_from(SourceMonitorAlert).where(SourceMonitorAlert.read_at.is_(None),SourceMonitorAlert.resolved_at.is_(None)))
        items=db.scalars(select(SourceMonitorAlert).where(*predicates).order_by(SourceMonitorAlert.updated_at.desc(),SourceMonitorAlert.id).offset((page-1)*20).limit(20))
        runs=db.scalars(select(SourceMonitorRun).order_by(SourceMonitorRun.day.desc()).limit(7))
        local=datetime.now(timezone.utc).astimezone(VIETNAM);today=db.get(SourceMonitorRun,local.date())
        return {'items':[item_payload(i) for i in items],'total':total,'unread':unread,'page':page,'pageSize':20,
            'runs':[{'day':r.day.isoformat(),'state':r.state,'details':r.details,'updatedAt':r.updated_at.isoformat()} for r in runs],
            'schedule':'06:00 Asia/Ho_Chi_Minh; after daily collection complete','sampleScope':'closed-month provincial scores only',
            'today':{'day':str(local.date()),'state':today.state if today else 'not-started' if local.hour>=6 else 'not-due'}}

@router.get('/{alert_id}')
def detail(alert_id:uuid.UUID,request:Request):
    with request.app.state.session_factory() as db:
        administrator(request,db);require_schema(db);item=db.get(SourceMonitorAlert,alert_id)
        if item is None:raise HTTPException(404,'Không tìm thấy cảnh báo.')
        result=item_payload(item,True)
        if item.kind=='structure':
            periods=db.execute(select(Snapshot.period_type,Snapshot.year,Snapshot.period_value).where(Snapshot.scope=='all',Snapshot.state=='complete').distinct().order_by(Snapshot.year.desc(),Snapshot.period_type,Snapshot.period_value)).all()
            result['recrawlPlan']={'execution':'requires-admin-review','scope':'all','periods':[
                {'type':p.period_type,'year':p.year,'value':p.period_value} for p in periods],
                'note':'Kế hoạch tham khảo, chưa tạo job; chỉ chuyển lịch sử ngày sang cơ cấu mới sau khi cào lại đủ và duyệt. Không sửa công thức đã lưu.'}
        return result

class Review(BaseModel):
    model_config=ConfigDict(extra='forbid')
    action:Literal['read','resolve']
    note:str=Field(default='',max_length=500)

@router.post('/{alert_id}/review')
def review(alert_id:uuid.UUID,payload:Review,request:Request):
    if payload.action=='resolve' and not payload.note.strip():raise HTTPException(422,'Vui lòng ghi nội dung xử lý cảnh báo.')
    with request.app.state.session_factory.begin() as db:
        actor=administrator(request,db,write=True);require_schema(db)
        item=db.scalar(select(SourceMonitorAlert).where(SourceMonitorAlert.id==alert_id).with_for_update())
        if item is None:raise HTTPException(404,'Không tìm thấy cảnh báo.')
        now=datetime.now(timezone.utc);item.read_at=item.read_at or now;item.reviewed_by=actor.id
        if payload.action=='resolve':item.resolved_at=now;item.details={**item.details,'resolutionNote':payload.note.strip()}
        audit(db,actor,'source-monitor.'+payload.action,alertId=str(item.id))
    return {'updated':True,'published':False}
