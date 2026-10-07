"""Versioned admin knowledge, pinned to each confirmed analysis; immutable safety rules."""
from contextlib import contextmanager
from datetime import datetime,timezone
from threading import RLock
from typing import Literal
from fastapi import APIRouter,HTTPException,Request,Response,Query
from pydantic import BaseModel,ConfigDict,Field,field_validator
from sqlalchemy import inspect,select,text
from .admin import administrator,audit
from .models import AnalysisConfigRevision,AnalysisConfigHead,AnalysisGroupConfigRevision,AnalysisFeatureControl,UserAccount
from .analysis_feature import feature_state,UNAVAILABLE
from .analysis_rules import LABELS,ACTIONS

DEFAULT_GUIDANCE=('Phân tích ý nghĩa quản lý, nội dung cần kiểm tra và hành động cụ thể cho từng chỉ tiêu. '
    'Hạn chế lặp khuyến nghị giữa nhóm và chỉ tiêu thành phần. Đề xuất bộ phận phối hợp và cách theo dõi kết quả. '
    'Phân biệt hồ sơ đang xử lý, hồ sơ đã hoàn thành và điều kiện của kỳ chưa kết thúc.')
router=APIRouter(prefix='/api/v1/admin/analysis-configuration',tags=['AI configuration'])
_LOCK=RLock()

GroupId=Literal['transparency','dvc-progress-tree','provide-online-tree','dossier-digitized','handling-satisfaction','formality-online-payment-tree']

def default_groups():
    return {key:dict(guidance=DEFAULT_GUIDANCE+'\n'+ACTIONS[key],knowledge='') for key in LABELS}

def group_schema_ready(db):
    return inspect(db.connection()).has_table('analysis_group_config_revisions')

def group_configuration(db,version):
    if not version or not group_schema_ready(db):return None
    rows=list(db.scalars(select(AnalysisGroupConfigRevision).where(AnalysisGroupConfigRevision.version==version)))
    if not rows:return None
    values=default_groups()
    values.update({row.group_id:dict(guidance=row.guidance,knowledge=row.knowledge) for row in rows})
    return values

def schema_ready(db):
    inspector=inspect(db.connection())
    return all(inspector.has_table(name) for name in ('analysis_config_revisions','analysis_config_head'))

def configuration(db):
    if schema_ready(db):
        head=db.get(AnalysisConfigHead,1)
        if head:
            row=db.get(AnalysisConfigRevision,head.version)
            if row is None:raise ValueError('Invalid analysis configuration revision')
            groups=group_configuration(db,row.version)
            if groups is not None:return dict(version=row.version,mode='groups',groups=groups)
            return dict(version=row.version,guidance=row.guidance,knowledge=row.knowledge)
    return dict(version=0,guidance=DEFAULT_GUIDANCE,knowledge='')

class ConfigurationSave(BaseModel):
    model_config=ConfigDict(extra='forbid')
    expectedVersion:int=Field(ge=0)
    groupId:GroupId|None=None
    guidance:str=Field(min_length=20,max_length=10000)
    knowledge:str=Field(default='',max_length=30000)
    note:str=Field(min_length=3,max_length=500)
    @field_validator('guidance','knowledge','note')
    @classmethod
    def plain_text(cls,value):
        if any(ord(c)<32 and c not in '\n\r\t' for c in value):raise ValueError('Unsupported control characters')
        value=value.strip()
        return value

@contextmanager
def save_lock(db):
    if db.bind.dialect.name=='postgresql':
        db.execute(text('SELECT pg_advisory_xact_lock(:key)'),{'key':7662000});yield
    else:
        with _LOCK:yield

@router.get('')
def read(request:Request,response:Response,version:int|None=Query(None,ge=0)):
    response.headers['Cache-Control']='no-store'
    with request.app.state.session_factory() as db:
        administrator(request,db);ready=schema_ready(db);current=configuration(db)
        selected=current
        if version is not None:
            if version==0:selected=dict(version=0,guidance=DEFAULT_GUIDANCE,knowledge='')
            elif not ready:raise HTTPException(503,'Cấu hình AI chưa được cài đặt.')
            else:
                row=db.get(AnalysisConfigRevision,version)
                if row is None:raise HTTPException(404,'Không tìm thấy phiên bản cấu hình.')
                selected=dict(version=row.version,guidance=row.guidance,knowledge=row.knowledge)
        history=[]
        if ready:
            rows=db.execute(select(AnalysisConfigRevision.version,AnalysisConfigRevision.note,
                AnalysisConfigRevision.created_at,UserAccount.display_name).join(UserAccount,
                UserAccount.id==AnalysisConfigRevision.actor_id).order_by(AnalysisConfigRevision.version.desc()).limit(20))
            history=[dict(version=v,note=n,at=at.isoformat(),actor=actor) for v,n,at,actor in rows]
        groups=group_configuration(db,selected['version'])
        if groups is None:groups=selected.get('groups',default_groups())
        legacy=None
        if selected['version'] and not group_configuration(db,selected['version']):
            legacy=dict(guidance=selected.get('guidance',''),knowledge=selected.get('knowledge',''))
        return {**selected,'groups':groups,'defaultGroups':default_groups(),
            'groupSchemaReady':ready and group_schema_ready(db),'legacyConfiguration':legacy,
            'feature':feature_state(db),'activeVersion':current['version'],'schemaReady':ready,'history':history,
            'defaultGuidance':DEFAULT_GUIDANCE,'rules':['Không tự tạo số liệu, công thức hoặc hứa chắc tăng điểm.',
                'Không suy đoán dữ liệu cấp xã từ dữ liệu tỉnh.',
                'Phân biệt hồ sơ đã/đang xử lý, điều kiện số hóa kết quả và thanh toán.',
                'Quá hạn và đánh giá không hài lòng đều ảnh hưởng hài lòng; không cộng trùng.',
                'Chỉ chạy khi người dùng xác nhận; 5 Credit mỗi nhóm được chọn, hoàn đủ Credit đã giữ nếu lượt thất bại.']}

@router.post('')
def save(payload:ConfigurationSave,request:Request,response:Response):
    response.headers['Cache-Control']='no-store'
    if len(payload.guidance)<20 or len(payload.note)<3:raise HTTPException(422,'Hướng dẫn hoặc ghi chú quá ngắn.')
    if payload.groupId and (len(payload.guidance)>4000 or len(payload.knowledge)>10000):
        raise HTTPException(422,'Mỗi nhóm tối đa 4.000 ký tự hướng dẫn và 10.000 ký tự kiến thức.')
    with request.app.state.session_factory.begin() as db:
        actor=administrator(request,db,write=True)
        if not schema_ready(db):raise HTTPException(503,'Cần nâng schema cấu hình AI trước khi lưu.')
        if payload.groupId and not group_schema_ready(db):raise HTTPException(503,'Cần nâng schema cấu hình theo nhóm trước khi lưu. Cấu hình hiện tại được giữ nguyên.')
        with save_lock(db):
            current=configuration(db)
            if payload.expectedVersion!=current['version']:
                raise HTTPException(409,'Cấu hình đã được cập nhật ở phiên khác. Tải lại trước khi lưu.')
            if current.get('mode')=='groups' and not payload.groupId:
                raise HTTPException(409,'Hệ thống đang cấu hình riêng từng nhóm. Tải lại giao diện để chọn nhóm cần sửa.')
            version=current['version']+1
            # Group edits do not rewrite the previous shared configuration or other groups.
            legacy=db.get(AnalysisConfigRevision,current['version']) if current['version'] else None
            guidance=(legacy.guidance if legacy else DEFAULT_GUIDANCE) if payload.groupId else payload.guidance
            knowledge=(legacy.knowledge if legacy else '') if payload.groupId else payload.knowledge
            db.add(AnalysisConfigRevision(version=version,guidance=guidance,knowledge=knowledge,
                note=payload.note,actor_id=actor.id,created_at=datetime.now(timezone.utc)))
            db.flush()
            if payload.groupId:
                groups=current.get('groups',default_groups())
                groups[payload.groupId]=dict(guidance=payload.guidance,knowledge=payload.knowledge)
                for key,value in groups.items():
                    db.add(AnalysisGroupConfigRevision(version=version,group_id=key,**value))
            head=db.get(AnalysisConfigHead,1)
            if head:head.version=version
            else:db.add(AnalysisConfigHead(id=1,version=version))
            audit(db,actor,'analysis_configuration_saved',version=version,group=payload.groupId)
        return {'version':version,'message':'Đã lưu. Áp dụng cho các lượt phân tích được xác nhận sau thời điểm này.'}

class FeatureSave(BaseModel):
    model_config=ConfigDict(extra='forbid')
    enabled:bool=Field(strict=True)
    expectedRevision:int=Field(ge=0)

@router.post('/feature')
def set_feature(payload:FeatureSave,request:Request,response:Response):
    from .analysis_queue import admission_lock
    response.headers['Cache-Control']='no-store'
    with request.app.state.session_factory.begin() as db:
        actor=administrator(request,db,write=True)
        with admission_lock(db):
            current=feature_state(db)
            if not current['schemaReady']:raise HTTPException(503,'Cần nâng schema bật/tắt phân tích AI trước khi sử dụng.')
            if payload.expectedRevision!=current['revision']:raise HTTPException(409,'Trạng thái đã được thay đổi ở phiên khác. Tải lại trước khi bật/tắt.')
            if payload.enabled==current['enabled']:return current
            row=db.get(AnalysisFeatureControl,1)
            if row is None:
                row=AnalysisFeatureControl(id=1,revision=0,actor_id=actor.id,updated_at=datetime.now(timezone.utc));db.add(row)
            row.enabled=payload.enabled;row.revision+=1;row.actor_id=actor.id;row.updated_at=datetime.now(timezone.utc)
            audit(db,actor,'analysis_feature_changed',enabled=row.enabled,revision=row.revision)
            return {'enabled':row.enabled,'revision':row.revision,'schemaReady':True,'message':'Đã bật Phân tích điểm số.' if row.enabled else UNAVAILABLE}
