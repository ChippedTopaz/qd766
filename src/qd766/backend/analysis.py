"""Explicit paid analysis; HTTP call never holds a database transaction open."""
import uuid
import logging
import httpx
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from threading import BoundedSemaphore
from typing import Annotated, Literal
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import inspect, select, func, or_, and_
from sqlalchemy.orm import Session, selectinload
from qd766.periods import PeriodSelection
from .models import GeminiAnalysis, AnalysisQueueEntry, Snapshot, Dataset, Entity
from .database import get_session
from .user_collection import account_for, valid_period
from .paid_requests import _locked_account
from .wallet_access import enabled, active_subscription
from .credit_wallet import reserve, finish, balance, WalletError, utc
from .analysis_rules import findings, VERSION, number
from .daily_history import history_payload
from . import gemini_client

router=APIRouter(prefix="/api/v1/me/analysis",tags=["analysis"])
Db=Annotated[Session,Depends(get_session)]
COST=20
SLOTS=BoundedSemaphore(2)

class AnalysisSelection(BaseModel):
    model_config=ConfigDict(extra="forbid")
    rootDepartmentId:uuid.UUID
    unitId:uuid.UUID
    periodType:Literal["month","quarter","year"]
    year:int=Field(ge=2026,le=2100)
    periodValue:int|None=Field(default=None,ge=1,le=12)

class AnalysisConfirmation(AnalysisSelection):
    token:uuid.UUID
    expectedCredits:Literal[20]

def context_of(selection):
    return selection.model_dump(mode="json",exclude={"token","expectedCredits"})

def authorize(account,selection):
    valid_period(selection.periodType,selection.year,selection.periodValue)
    national=account.role=="admin" or account.access_tier=="national"
    if not national and account.root_department_id!=selection.rootDepartmentId:
        raise HTTPException(403,"Tỉnh không thuộc phạm vi tài khoản.")
    if account.role!="admin" and account.access_tier=="agency" and account.unit_department_id!=selection.unitId:
        raise HTTPException(403,"Cơ quan không thuộc phạm vi tài khoản.")

def recover_interrupted(db,account_id,now):
    # Same account lock used for admission/settlement. No provider retry or second charge.
    for row in db.scalars(select(GeminiAnalysis).where(GeminiAnalysis.account_id==account_id,
            GeminiAnalysis.state=="running",GeminiAnalysis.created_at<now-timedelta(minutes=5))):
        if inspect(db.connection()).has_table('analysis_queue_entries') and db.get(AnalysisQueueEntry,row.id):continue
        finish(db,account_id,request_key="analysis:"+str(row.id),outcome="refund",now=now)
        row.state="failed";row.finished_at=now

def source_evidence(db,selection):
    query=select(Snapshot).where(Snapshot.root_department_id==selection.rootDepartmentId,
        Snapshot.scope=="all",Snapshot.period_type==selection.periodType,Snapshot.year==selection.year,
        Snapshot.period_value==selection.periodValue).order_by(Snapshot.created_at.desc()).limit(1)
    snapshot=db.scalar(query)
    if snapshot is None:raise HTTPException(409,"Chưa có dữ liệu chi tiết để phân tích.")
    pairs=db.execute(select(Dataset,Entity).join(Entity).where(Dataset.snapshot_id==snapshot.id,
        Entity.department_id==selection.unitId).options(selectinload(Entity.metrics),selectinload(Entity.department))).all()
    groups=[];name=""
    for dataset,entity in pairs:
        name=entity.department.name
        groups.append(dict(id=dataset.group_name,score=float(entity.api_score) if entity.api_score is not None else None,
            maximum=float(entity.api_max_score) if entity.api_max_score is not None else None,parameters=entity.parameters,
            metrics=[dict(code=m.code,name=m.name,numerator=float(m.numerator) if m.numerator is not None else None,
                denominator=float(m.denominator) if m.denominator is not None else None,
                score=float(m.api_score) if m.api_score is not None else None,
                maximum=float(m.api_max_score) if m.api_max_score is not None else None) for m in entity.metrics]))
    if not groups:raise HTTPException(409,"Cơ quan chưa có dữ liệu trong kỳ này.")
    days=history_payload(db,selection.rootDepartmentId,selection.unitId,
        PeriodSelection(selection.periodType,selection.year,selection.periodValue),3)["days"] if inspect(db.bind).has_table("daily_observations") else []
    # Do not compare observations captured after the analyzed snapshot.
    days=[day for day in days if utc(datetime.fromisoformat(day["capturedAt"]))<=utc(snapshot.created_at)]
    try:cards=findings(groups,days)
    except ValueError as exc:raise HTTPException(409,str(exc)) from exc
    period=PeriodSelection(selection.periodType,selection.year,selection.periodValue)
    start,end=period.date_range()
    captured_date=utc(snapshot.created_at).astimezone(ZoneInfo('Asia/Ho_Chi_Minh')).date().isoformat()
    # Aggregate numeric data only: no raw payloads, credentials or dossier identities.
    context_groups=[{**group,'parameters':{key:value for key,value in group['parameters'].items()
        if number(value) is not None}} for group in groups]
    from .analysis_configuration import configuration
    analysis_configuration=configuration(db)
    return {"version":VERSION,"snapshotId":str(snapshot.id),"capturedAt":utc(snapshot.created_at).isoformat(),
        "organization":name,"context":context_of(selection),"findings":cards,
        "groups":context_groups,"reportingPeriod":{"start":start,"end":end,"capturedDate":captured_date,
            "endedAtCapture":captured_date>end},
        "analysisConfiguration":analysis_configuration,
        "coverage":len(groups),"limitations":["Số liệu tổng hợp không xác định được trạng thái từng hồ sơ.",
            "Kỳ đang diễn ra có thể bị ảnh hưởng bởi hồ sơ chưa có kết quả hoặc chưa đến bước thanh toán.",
            "Biến động ngày chỉ tham khảo; chưa xác minh tự động được mọi thay đổi công thức nguồn."]}

def serialize(row,db):
    values=balance(db,row.account_id,now=datetime.now(timezone.utc))
    position=db.scalar(select(func.count()).select_from(GeminiAnalysis).where(GeminiAnalysis.state=='queued',
        or_(GeminiAnalysis.created_at<row.created_at,and_(GeminiAnalysis.created_at==row.created_at,GeminiAnalysis.id<=row.id)))) if row.state=='queued' else None
    return {"id":str(row.id),"requestToken":str(row.request_token),"state":row.state,"context":row.context,"createdAt":utc(row.created_at).isoformat(),
        "availableCredits":values["available"],"reservedCredits":values["reserved"],
        "credits":COST if row.state=="ready" else 0,"heldCredits":COST if row.state in {'queued','running'} else 0,
        "queuePosition":position,"queueWaitMinutes":10,
        "result":row.result,"capturedAt":row.evidence["capturedAt"],"message":
        "Đang chờ phân tích. Credit được giữ, chưa ghi nhận thu." if row.state=='queued' else
        "Đã hủy lượt phân tích. Credit đã được hoàn." if row.state=='cancelled' else
        "Phân tích không hoàn tất hoặc hết thời gian chờ. Credit đã được hoàn." if row.state=="failed" else
        "Lượt phân tích đang xử lý. Credit chỉ ghi nhận khi kết quả được lưu thành công." if row.state=="running" else ""}

@router.get("/latest")
def latest(request:Request,response:Response,db:Db,root_department_id:uuid.UUID,unit_id:uuid.UUID,
           period_type:Literal["month","quarter","year"],year:int,period_value:int|None=None):
    response.headers["Cache-Control"]="no-store"
    account=account_for(request,db)
    selection=AnalysisSelection(rootDepartmentId=root_department_id,unitId=unit_id,periodType=period_type,year=year,periodValue=period_value)
    authorize(account,selection)
    if not inspect(db.bind).has_table("gemini_analyses"):return {"analysis":None}
    query=select(GeminiAnalysis).where(GeminiAnalysis.account_id==account.id)
    for key,value in context_of(selection).items():
        query=query.where(GeminiAnalysis.context[key].as_string()==value) if isinstance(value,str) else query.where(
            GeminiAnalysis.context[key].as_integer()==value)
    row=db.scalar(query.order_by(GeminiAnalysis.created_at.desc()).limit(1))
    # GET remains read-only. Interrupted refunds are reconciled on explicit POST/recovery tool.
    return {"analysis":serialize(row,db) if row else None}

@router.post("")
def analyze(selection:AnalysisConfirmation,request:Request,response:Response,db:Db):
    response.headers["Cache-Control"]="no-store"
    account=account_for(request,db);authorize(account,selection)
    if not inspect(db.bind).has_table("gemini_analyses"):raise HTTPException(503,"Tính năng phân tích chưa được cài đặt.")
    if request.app.state.settings.gemini_queue_enabled:
        return enqueue(selection,request,response,db,account)
    _locked_account(db,account.id)
    recover_interrupted(db,account.id,datetime.now(timezone.utc))
    old=db.scalar(select(GeminiAnalysis).where(GeminiAnalysis.account_id==account.id,GeminiAnalysis.request_token==selection.token))
    if old:
        if old.context!=context_of(selection):raise HTTPException(409,"Mã xác nhận không khớp lựa chọn.")
        db.commit();return serialize(old,db)
    settings=request.app.state.settings
    if not settings.gemini_analysis_enabled or not settings.gemini_api_key or not settings.gemini_model:
        raise HTTPException(503,"Phân tích Gemini chưa được cấu hình. Không sử dụng Credit.")
    if settings.wallet_requests_paused:raise HTTPException(503,"Tạm dừng yêu cầu sử dụng Credit mới.")
    now=datetime.now(timezone.utc)
    if not enabled(db,account.id):raise HTTPException(403,"Tài khoản chưa được kích hoạt ví Credit.")
    if not active_subscription(db,account.id,now=now):raise HTTPException(403,"Subscription đã hết hạn. Vui lòng gia hạn để phân tích.")
    if db.scalar(select(GeminiAnalysis.id).where(GeminiAnalysis.account_id==account.id,GeminiAnalysis.state=="running")):
        raise HTTPException(409,"Tài khoản đang có một lượt phân tích. Vui lòng chờ hoàn thành.")
    if balance(db,account.id,now=now)["available"]<COST:raise HTTPException(402,"Tài khoản của bạn không đủ Credit để phân tích (20 Credit).")
    evidence=source_evidence(db,selection)
    if not evidence["findings"]:raise HTTPException(409,"Chưa đủ phát hiện để phân tích. Không sử dụng Credit.")
    if not SLOTS.acquire(blocking=False):raise HTTPException(503,"Phân tích đang bận. Vui lòng thử lại; chưa sử dụng Credit.")
    try:
        row=GeminiAnalysis(id=uuid.uuid4(),account_id=account.id,request_token=selection.token,context=context_of(selection),
            evidence=evidence,model=settings.gemini_model,created_at=now,state="running")
        db.add(row)
        try:reserve(db,account.id,COST,request_key="analysis:"+str(row.id),now=now);db.commit()
        except WalletError as exc:db.rollback();raise HTTPException(402,"Không đủ Credit để phân tích.") from exc
        job_id=row.id;account_id=account.id
        # No open DB transaction during Gemini. A client disconnect cannot create a duplicate run.
        try:
            cards=gemini_client.generate(settings,evidence)
        except Exception as error:
            # Never include exception text, provider body, prompt or credentials.
            status=error.response.status_code if isinstance(error,httpx.HTTPStatusError) else None
            logging.getLogger(__name__).warning('GEMINI_ANALYSIS_FAILED id=%s type=%s http_status=%s',
                job_id,type(error).__name__,status)
            db.rollback();_locked_account(db,account_id);row=db.get(GeminiAnalysis,job_id,populate_existing=True)
            if row.state=="running":
                finish(db,account_id,request_key="analysis:"+str(job_id),outcome="refund",now=datetime.now(timezone.utc))
                row.state="failed";row.finished_at=datetime.now(timezone.utc);db.commit()
            return serialize(row,db)
        try:
            _locked_account(db,account_id);row=db.get(GeminiAnalysis,job_id,populate_existing=True)
            if row.state=="running":
                row.result={"cards":cards,"limitations":evidence["limitations"],"version":VERSION,"model":settings.gemini_model,
                    'configurationVersion':evidence.get('analysisConfiguration',{}).get('version',0)}
                row.state="ready";row.finished_at=datetime.now(timezone.utc)
                finish(db,account_id,request_key="analysis:"+str(job_id),outcome="charge",now=row.finished_at)
                db.commit() # Result and charge atomically durable.
            return serialize(row,db)
        except Exception:
            db.rollback()
            # Leave durable running hold for safe reconciliation; never charge without saved result.
            raise HTTPException(503,"Chưa xác nhận được kết quả. Hãy xem lại lượt phân tích trước khi gửi mới.")
    finally:SLOTS.release()


def enqueue(selection,request,response,db,account):
    from .analysis_queue import admission_lock,check_capacity,recover_account,WAIT_MINUTES
    settings=request.app.state.settings
    if not inspect(db.bind).has_table('analysis_queue_entries'):
        raise HTTPException(503,'Hàng chờ phân tích chưa được cài đặt. Chưa giữ Credit.')
    with admission_lock(db):
        _locked_account(db,account.id);now=datetime.now(timezone.utc)
        recover_account(db,account.id,now)
        old=db.scalar(select(GeminiAnalysis).where(GeminiAnalysis.account_id==account.id,GeminiAnalysis.request_token==selection.token))
        if old:
            if old.context!=context_of(selection):raise HTTPException(409,'Mã xác nhận không khớp lựa chọn.')
            db.commit();response.status_code=202 if old.state in {'queued','running'} else 200
            return serialize(old,db)
        if not settings.gemini_analysis_enabled or not settings.gemini_api_key or not settings.gemini_model:
            raise HTTPException(503,'Phân tích chưa được cấu hình. Chưa giữ Credit.')
        if settings.wallet_requests_paused:raise HTTPException(503,'Tạm dừng yêu cầu sử dụng Credit mới.')
        if not enabled(db,account.id):raise HTTPException(403,'Tài khoản chưa được kích hoạt ví Credit.')
        if not active_subscription(db,account.id,now=now):raise HTTPException(403,'Subscription đã hết hạn.')
        if db.scalar(select(GeminiAnalysis.id).where(GeminiAnalysis.account_id==account.id,GeminiAnalysis.state.in_(['queued','running']))):
            raise HTTPException(409,'Tài khoản đang có một lượt chờ hoặc đang phân tích.')
        check_capacity(db)
        if balance(db,account.id,now=now)['available']<COST:raise HTTPException(402,'Tài khoản của bạn không đủ Credit để phân tích (20 Credit).')
        evidence=source_evidence(db,selection)
        if not evidence['findings']:raise HTTPException(409,'Chưa đủ dữ liệu để phân tích. Chưa giữ Credit.')
        row=GeminiAnalysis(id=uuid.uuid4(),account_id=account.id,request_token=selection.token,
            context=context_of(selection),evidence=evidence,model=settings.gemini_model,created_at=now,state='queued')
        db.add(row);db.flush()
        db.add(AnalysisQueueEntry(analysis_id=row.id,expires_at=now+timedelta(minutes=WAIT_MINUTES)))
        try:reserve(db,account.id,COST,request_key='analysis:'+str(row.id),now=now);db.commit()
        except WalletError as error:db.rollback();raise HTTPException(402,'Không đủ Credit để phân tích.') from error
        response.status_code=202
        return serialize(row,db)


@router.get('/{analysis_id}/status')
def status(analysis_id:uuid.UUID,request:Request,response:Response,db:Db):
    response.headers['Cache-Control']='no-store'
    account=account_for(request,db)
    row=db.scalar(select(GeminiAnalysis).where(GeminiAnalysis.id==analysis_id,GeminiAnalysis.account_id==account.id))
    if row is None:raise HTTPException(404,'Không tìm thấy lượt phân tích.')
    authorize(account,AnalysisSelection(**row.context))
    return serialize(row,db)


@router.post('/cancel')
def cancel(selection:AnalysisConfirmation,request:Request,response:Response,db:Db):
    response.headers['Cache-Control']='no-store'
    account=account_for(request,db);authorize(account,selection)
    _locked_account(db,account.id)
    row=db.scalar(select(GeminiAnalysis).where(GeminiAnalysis.account_id==account.id,GeminiAnalysis.request_token==selection.token))
    if row is None:raise HTTPException(404,'Không tìm thấy lượt phân tích.')
    if row.context!=context_of(selection):raise HTTPException(409,'Lựa chọn không khớp lượt phân tích.')
    if row.state=='queued':
        now=datetime.now(timezone.utc)
        finish(db,account.id,request_key='analysis:'+str(row.id),outcome='refund',now=now)
        row.state='cancelled';row.finished_at=now;db.commit()
    elif row.state=='running':raise HTTPException(409,'Lượt phân tích đã bắt đầu; không thể hủy khi đang xử lý.')
    return serialize(row,db)
