"""Admin-managed reference text only; never changes scoring or collection logic."""
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
import json
from fastapi import APIRouter, HTTPException, Request, Response, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import inspect, select, text
from .admin import administrator, audit
from .analysis_configuration import save_lock
from .models import FormulaConfigRevision, FormulaConfigHead, UserAccount

router = APIRouter(tags=['Formula reference configuration'])
SEED = json.loads(Path(__file__).with_name('formula_seed.json').read_text(encoding='utf-8'))

def upgrade_payment_content(content):
    """Add the approved payment component without replacing authored reference text.

    Upgrade only the legacy two-item payment group. Once saved with three items,
    all administrator edits (including point limits) remain under their control.
    Historical revisions are not rewritten.
    """
    result=deepcopy(content)
    groups=result.get('groups',[])
    if not isinstance(groups,list):return result
    for group in groups:
        if not isinstance(group,dict):continue
        if group.get('id')!='formality-online-payment-tree':continue
        items=group.get('items',[])
        if not isinstance(items,list) or any(not isinstance(item,dict) for item in items):continue
        if [item.get('id') for item in items]!=['3.5','3.6']:continue
        base=next(g for g in SEED['groups'] if g['id']==group['id'])
        added=next((i for i in base['items'] if i['id']=='3.5b'),None)
        if added is None:continue
        items[0]['maximum']=2;items[0]['target']=80
        items[1]['maximum']=6;items[1]['target']=None
        items.insert(1,deepcopy(added))
    return result

def ready(db):
    inspector = inspect(db.connection())
    return all(inspector.has_table(t) for t in ('formula_config_revisions', 'formula_config_head'))

def current(db):
    head = db.get(FormulaConfigHead, 1) if ready(db) else None
    if head:
        row = db.get(FormulaConfigRevision, head.version)
        return dict(version=head.version, configuration=upgrade_payment_content(row.content))
    return dict(version=0, configuration=deepcopy(SEED))

class Save(BaseModel):
    model_config = ConfigDict(extra='forbid')
    expectedVersion: int = Field(ge=0)
    configuration: dict
    note: str = Field(min_length=3, max_length=500)

def validate_content(content):
    """Fixed membership prevents accidental omissions; bounded plain text, not HTML."""
    def fail(): raise HTTPException(422, 'Nội dung công thức không hợp lệ. Giữ đủ 6 nhóm và các chỉ tiêu hiện tại.')
    def walk(value, depth=0):
        if depth > 12: fail()
        if isinstance(value, str):
            if len(value)>30000 or any(ord(c)<32 and c not in '\r\n\t' for c in value): fail()
        elif isinstance(value, list):
            if len(value)>300: fail()
            for item in value: walk(item, depth+1)
        elif isinstance(value, dict):
            if len(value)>40: fail()
            for key,item in value.items(): walk(key,depth+1);walk(item,depth+1)
        elif value is not None and not isinstance(value,(int,float,bool)): fail()
    walk(content)
    if len(json.dumps(content,ensure_ascii=False))>600000: fail()
    if set(content)!=set(SEED): fail()
    if not isinstance(content['guide'],list) or any(not isinstance(line,str) for line in content['guide']): fail()
    source=content.get('source',{})
    if not isinstance(source,dict) or set(source)!=set(SEED['source']) or any(not isinstance(v,str) or not v.strip() for v in source.values()): fail()
    groups=content.get('groups')
    if not isinstance(groups,list) or len(groups)!=6: fail()
    for group, original in zip(groups,SEED['groups']):
        if not isinstance(group,dict) or set(group)!=set(original) or group['id']!=original['id']: fail()
        if not isinstance(group['name'],str) or not group['name'].strip(): fail()
        if type(group['maximum']) not in (int,float) or not 0<=group['maximum']<=100: fail()
        if not isinstance(group['items'],list) or len(group['items'])!=len(original['items']): fail()
        for item,base in zip(group['items'],original['items']):
            if not isinstance(item,dict) or set(item)!=set(base) or item['id']!=base['id']: fail()
            for key in ('title','numerator','denominator','equationLabel','clarification','businessHeading','versionNote','mathNote','symbols'):
                if not isinstance(item[key],str): fail()
            if not item['title'].strip() or not item['numerator'].strip(): fail()
            for key in ('maximum','target'):
                if key in item and item[key] is not None and (type(item[key]) not in (int,float) or not 0<=item[key]<=100): fail()
            if 'target' in item and item['target'] is not None and item['target']==0: fail()
            for key in ('multiplier','caution'):
                if key in item and not isinstance(item[key],str): fail()
            for key in ('businessLines','rules'):
                if not isinstance(item[key],list) or any(not isinstance(line,str) for line in item[key]): fail()
            doc=item.get('document',{})
            if not isinstance(doc,dict) or set(doc)!=set(base['document']): fail()
            for key in ('id','title','group'):
                if not isinstance(doc[key],str): fail()
            for key in ('business','notes','dataSources'):
                if not isinstance(doc[key],list) or any(not isinstance(line,str) for line in doc[key]): fail()
            if not isinstance(item['extras'],list) or len(item['extras'])>10: fail()
            for extra in item['extras']:
                if not isinstance(extra,dict) or not {'label','numerator','denominator'}<=set(extra) or not set(extra)<={'label','numerator','denominator','operator','multiplier'} or any(not isinstance(v,str) for v in extra.values()): fail()
                if 'operator' in extra and extra['operator'] not in ('add','subtract','multiply','divide'): fail()

@router.get('/api/v1/formula-reference')
def reference(request:Request,response:Response):
    response.headers['Cache-Control']='no-store'
    with request.app.state.session_factory() as db:
        return current(db)

@router.get('/api/v1/admin/formula-configuration')
def read(request:Request,response:Response,version:int|None=Query(None,ge=0)):
    response.headers['Cache-Control']='no-store'
    with request.app.state.session_factory() as db:
        administrator(request,db)
        value=current(db);active=value['version'];history=[]
        if ready(db):
            rows=db.execute(select(FormulaConfigRevision.version,FormulaConfigRevision.note,
                FormulaConfigRevision.created_at,UserAccount.display_name).join(UserAccount,
                UserAccount.id==FormulaConfigRevision.actor_id,isouter=True).order_by(FormulaConfigRevision.version.desc()).limit(50))
            history=[dict(version=v,note=n,at=at.isoformat(),actor=actor or 'Bản gốc') for v,n,at,actor in rows]
        if version is not None:
            if version==0:value=dict(version=0,configuration=deepcopy(SEED))
            else:
                row=db.get(FormulaConfigRevision,version) if ready(db) else None
                if not row:raise HTTPException(404,'Không tìm thấy phiên bản công thức.')
                value=dict(version=version,configuration=deepcopy(row.content))
        return {**value,'activeVersion':active,'schemaReady':ready(db),'history':history}

@router.post('/api/v1/admin/formula-configuration')
def save(payload:Save,request:Request,response:Response):
    response.headers['Cache-Control']='no-store'
    with request.app.state.session_factory.begin() as db:
        actor=administrator(request,db,write=True)
        if not ready(db):raise HTTPException(503,'Cần nâng schema Công thức tính trước khi lưu. Nội dung hiện tại được giữ nguyên.')
        payload.configuration=upgrade_payment_content(payload.configuration)
        validate_content(payload.configuration)
        if len(payload.note.strip())<3:raise HTTPException(422,'Cần ghi chú thay đổi.')
        with save_lock(db):
            value=current(db)
            if payload.expectedVersion!=value['version']:raise HTTPException(409,'Công thức đã được sửa ở phiên khác. Tải lại và đối chiếu trước khi lưu.')
            if value['configuration']==payload.configuration:return {'version':value['version'],'message':'Không có thay đổi.'}
            version=value['version']+1
            db.add(FormulaConfigRevision(version=version,content=payload.configuration,note=payload.note.strip(),
                actor_id=actor.id,created_at=datetime.now(timezone.utc)));db.flush()
            head=db.get(FormulaConfigHead,1)
            if head:head.version=version
            else:db.add(FormulaConfigHead(id=1,version=version))
            audit(db,actor,'formula_configuration_saved',version=version)
            return {'version':version,'message':'Đã lưu. Nội dung mới hiển thị khi người dùng mở Công thức tính; điểm số và logic tính điểm không đổi.'}
