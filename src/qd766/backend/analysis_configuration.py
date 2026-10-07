"""Versioned admin knowledge, pinned to each confirmed analysis; immutable safety rules."""
from contextlib import contextmanager
from datetime import datetime,timezone
from threading import RLock
from fastapi import APIRouter,HTTPException,Request,Response,Query
from pydantic import BaseModel,ConfigDict,Field,field_validator
from sqlalchemy import inspect,select,text
from .admin import administrator,audit
from .models import AnalysisConfigRevision,AnalysisConfigHead,UserAccount

DEFAULT_GUIDANCE=('Phân tích ý nghĩa quản lý, nội dung cần kiểm tra và hành động cụ thể cho từng chỉ tiêu. '
    'Hạn chế lặp khuyến nghị giữa nhóm và chỉ tiêu thành phần. Đề xuất bộ phận phối hợp và cách theo dõi kết quả. '
    'Phân biệt hồ sơ đang xử lý, hồ sơ đã hoàn thành và điều kiện của kỳ chưa kết thúc.')
router=APIRouter(prefix='/api/v1/admin/analysis-configuration',tags=['AI configuration'])
_LOCK=RLock()

def schema_ready(db):
    inspector=inspect(db.connection())
    return all(inspector.has_table(name) for name in ('analysis_config_revisions','analysis_config_head'))

def configuration(db):
    if schema_ready(db):
        head=db.get(AnalysisConfigHead,1)
        if head:
            row=db.get(AnalysisConfigRevision,head.version)
            if row is None:raise ValueError('Invalid analysis configuration revision')
            return dict(version=row.version,guidance=row.guidance,knowledge=row.knowledge)
    return dict(version=0,guidance=DEFAULT_GUIDANCE,knowledge='')

class ConfigurationSave(BaseModel):
    model_config=ConfigDict(extra='forbid')
    expectedVersion:int=Field(ge=0)
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
        return {**selected,'activeVersion':current['version'],'schemaReady':ready,'history':history,
            'defaultGuidance':DEFAULT_GUIDANCE,'rules':['Không tự tạo số liệu, công thức hoặc hứa chắc tăng điểm.',
                'Không suy đoán dữ liệu cấp xã từ dữ liệu tỉnh.',
                'Phân biệt hồ sơ đã/đang xử lý, điều kiện số hóa kết quả và thanh toán.',
                'Quá hạn và đánh giá không hài lòng đều ảnh hưởng hài lòng; không cộng trùng.',
                'Chỉ chạy khi người dùng xác nhận; giữ nguyên 20 Credit và quy tắc hoàn Credit.']}

@router.post('')
def save(payload:ConfigurationSave,request:Request,response:Response):
    response.headers['Cache-Control']='no-store'
    if len(payload.guidance)<20 or len(payload.note)<3:raise HTTPException(422,'Hướng dẫn hoặc ghi chú quá ngắn.')
    with request.app.state.session_factory.begin() as db:
        actor=administrator(request,db,write=True)
        if not schema_ready(db):raise HTTPException(503,'Cần nâng schema cấu hình AI trước khi lưu.')
        with save_lock(db):
            current=configuration(db)
            if payload.expectedVersion!=current['version']:
                raise HTTPException(409,'Cấu hình đã được cập nhật ở phiên khác. Tải lại trước khi lưu.')
            version=current['version']+1
            db.add(AnalysisConfigRevision(version=version,guidance=payload.guidance,knowledge=payload.knowledge,
                note=payload.note,actor_id=actor.id,created_at=datetime.now(timezone.utc)))
            db.flush();head=db.get(AnalysisConfigHead,1)
            if head:head.version=version
            else:db.add(AnalysisConfigHead(id=1,version=version))
            audit(db,actor,'analysis_configuration_saved',version=version)
        return {'version':version,'message':'Đã lưu. Áp dụng cho các lượt phân tích được xác nhận sau thời điểm này.'}
