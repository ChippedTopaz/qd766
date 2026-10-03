"""Account-owned TTHC requests. No raw job IDs or shared-cache availability exposed."""
from __future__ import annotations
import base64
import hashlib
import hmac
import json
import time
import uuid
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from pydantic import BaseModel, Field, ConfigDict
from sqlalchemy import select,func,update
from sqlalchemy.orm import Session
from qd766.periods import PeriodSelection
from qd766.province_roots import load_province_roots
from qd766.province_catalog import ProvinceCatalogError
from .auth import current_session, SESSION_COOKIE
from .database import get_session
from .models import PaidDataRequest, Formality, Snapshot, CollectionJob,UserNotification
from datetime import datetime,timezone
from .paid_requests import create_paid_data_request, PaidRequestError

router=APIRouter(prefix="/api/v1/me",tags=["user-collection"])
Db=Annotated[Session,Depends(get_session)]

class Selection(BaseModel):
    model_config=ConfigDict(extra="forbid")
    periodType:str=Field(pattern="^(month|quarter|year)$")
    year:int=Field(ge=2000,le=2200)
    periodValue:int|None=None
    formalityIds:list[uuid.UUID]=Field(min_length=1,max_length=50)

class Confirmation(BaseModel):
    model_config=ConfigDict(extra="forbid")
    quote:str=Field(max_length=30000)
    token:uuid.UUID

class NotificationRead(BaseModel):
    model_config=ConfigDict(extra="forbid")
    requestIds:list[uuid.UUID]=Field(max_length=200)

def account_for(request:Request,db:Session,*,require_collect:bool=False):
    if not request.app.state.settings.paid_requests_enabled:
        raise HTTPException(403,"Khai thác theo tài khoản chưa được mở.")
    login,account=current_session(db,request.cookies.get(SESSION_COOKIE))
    if account is None:raise HTTPException(401,"Vui lòng đăng nhập.")
    if account.root_department_id is None:raise HTTPException(403,"Tài khoản chưa được gán tỉnh.")
    if request.app.state.settings.invite_required and not account.trial_admitted:
        raise HTTPException(403,"Tài khoản chưa được mời dùng thử.")
    if require_collect:
        from .collection_permissions import can_collect
        if not can_collect(db,account.id):raise HTTPException(403,"Tài khoản chưa được cấp quyền khai thác TTHC.")
    if request.method=="POST" and not hmac.compare_digest(request.headers.get("X-QD766-CSRF",""),login.csrf_token):
        raise HTTPException(403,"Xác nhận phiên không hợp lệ.")
    return account

def own_requests(db,account,kind,year,value):
    statement=select(PaidDataRequest).where(PaidDataRequest.account_id==account.id,
        PaidDataRequest.root_department_id==account.root_department_id,
        PaidDataRequest.period_type==kind,PaidDataRequest.year==year)
    return statement.where(PaidDataRequest.period_value.is_(None) if value is None else PaidDataRequest.period_value==value)

def entitlement(db,account,kind,year,value,formality_id):
    return db.scalar(own_requests(db,account,kind,year,value).where(
        PaidDataRequest.formality_id==formality_id,PaidDataRequest.state.in_(("reserved","waiting","ready"))))

def valid_period(kind,year,value):
    try:PeriodSelection(kind,year,value).validate_collectable()
    except ValueError as error:raise HTTPException(422,str(error)) from error

def resolve_items(request,account,selection):
    valid_period(selection.periodType,selection.year,selection.periodValue)
    root=next((r for r in load_province_roots().values() if r.root_department_id==account.root_department_id),None)
    if root is None:raise HTTPException(409,"Chưa có cấu hình tỉnh cho tài khoản.")
    try:
        catalog,_=request.app.state.province_catalog_cache.get_or_load(root.province_code+":internal=true",
            lambda:request.app.state.province_catalog_client.load(root.province_code,include_internal=True))
    except ProvinceCatalogError as error:raise HTTPException(503,"Chưa đọc được danh mục TTHC chuẩn.") from error
    by_id={item.id:item for item in catalog.select()}
    ids=list(dict.fromkeys(selection.formalityIds))
    if any(str(item) not in by_id for item in ids):raise HTTPException(422,"TTHC không thuộc danh mục áp dụng của tỉnh.")
    return root,[by_id[str(item)] for item in ids]

def signing_key(request):return request.app.state.settings.google_client_secret.encode()
def encode_quote(request,claims):
    body=base64.urlsafe_b64encode(json.dumps(claims,separators=(",",":"),ensure_ascii=True).encode()).decode()
    return body+"."+hmac.new(signing_key(request),body.encode(),hashlib.sha256).hexdigest()
def decode_quote(request,token):
    try:
        body,signature=token.rsplit(".",1)
        if not hmac.compare_digest(signature,hmac.new(signing_key(request),body.encode(),hashlib.sha256).hexdigest()):raise ValueError()
        claims=json.loads(base64.urlsafe_b64decode(body))
        if claims["expires"]<time.time():raise ValueError()
        return claims
    except (ValueError,KeyError,TypeError):raise HTTPException(409,"Xác nhận chi phí đã hết hạn hoặc không hợp lệ; hãy lấy báo giá lại.")

@router.post("/collection-quote")
def quote(selection:Selection,request:Request,db:Db):
    account=account_for(request,db,require_collect=True)
    if account.plan not in {"paid","admin"} and not request.app.state.settings.trial_credits_enabled:
        raise HTTPException(403,"Tài khoản chưa được phép khai thác theo credit.")
    root,items=resolve_items(request,account,selection)
    cost=request.app.state.settings.formality_credit_cost
    rows=[]
    for item in items:
        owned=entitlement(db,account,selection.periodType,selection.year,selection.periodValue,uuid.UUID(item.id))
        rows.append({"id":item.id,"code":item.code,"name":item.name,"cost":0 if owned else cost,"owned":owned is not None})
    total=sum(row["cost"] for row in rows)
    claims={"account":str(account.id),"root":str(root.root_department_id),"expires":int(time.time())+600,
        "selection":selection.model_dump(mode="json"),"unitCost":cost,"maximumCost":total}
    return {"quote":encode_quote(request,claims),"items":rows,"totalCredits":total,"availableCredits":account.credit_balance}

@router.post("/formality-requests",status_code=202)
def create_requests(payload:Confirmation,request:Request,db:Db):
    account=account_for(request,db,require_collect=True);claims=decode_quote(request,payload.quote)
    if claims["account"]!=str(account.id) or claims["root"]!=str(account.root_department_id):raise HTTPException(403,"Xác nhận không thuộc tài khoản này.")
    if claims["unitCost"]!=request.app.state.settings.formality_credit_cost:raise HTTPException(409,"Chi phí đã thay đổi; hãy xác nhận lại.")
    selection=Selection.model_validate(claims["selection"])
    root,items=resolve_items(request,account,selection)
    # Serialize account mutations, and never charge more than the displayed quote.
    from .paid_requests import _locked_account
    account=_locked_account(db,account.id)
    from .collection_permissions import can_collect
    if not account.active or not can_collect(db,account.id):raise HTTPException(403,"Quyền khai thác đã được thu hồi.")
    total=sum(0 if entitlement(db,account,selection.periodType,selection.year,selection.periodValue,uuid.UUID(item.id)) else claims["unitCost"] for item in items)
    if total>claims["maximumCost"]:raise HTTPException(409,"Quyền khai thác đã thay đổi; hãy xác nhận chi phí lại.")
    rows=[]
    try:
        for item in items:
            if db.get(Formality,uuid.UUID(item.id)) is None:
                from sqlalchemy.dialects.postgresql import insert as pg_insert
                from sqlalchemy.dialects.sqlite import insert as sqlite_insert
                insert=pg_insert if db.get_bind().dialect.name=="postgresql" else sqlite_insert
                db.execute(insert(Formality).values(id=uuid.UUID(item.id),code=item.code,name=item.name,attributes={"field":item.field})
                    .on_conflict_do_nothing(index_elements=[Formality.id]))
            paid,_=create_paid_data_request(db,account_id=account.id,province_code=root.province_code,
                root_department_id=root.root_department_id,formality_id=uuid.UUID(item.id),period_type=selection.periodType,
                year=selection.year,period_value=selection.periodValue,credit_cost=claims["unitCost"],
                idempotency_token=f"{payload.token}:{item.id}",allow_trial=request.app.state.settings.trial_credits_enabled)
            rows.append(serialize_request(db,paid))
        db.commit()
    except PaidRequestError as error:
        db.rollback();raise HTTPException(409,"Chưa thể thực hiện: kiểm tra credit hoặc kết nối nguồn. Không ghi nhận thu credit.") from error
    return {"items":rows,"availableCredits":account.credit_balance,"reservedCredits":account.credit_reserved}

def serialize_request(db,paid):
    formality=db.get(Formality,paid.formality_id)
    job=db.get(CollectionJob,paid.collection_job_id) if paid.collection_job_id else None
    progress="running" if paid.state=="waiting" and job is not None and job.state=="running" else paid.state
    return {"id":str(paid.id),"state":progress,"formalityId":str(paid.formality_id),
        "code":formality.code,"name":formality.name,"periodType":paid.period_type,"year":paid.year,"periodValue":paid.period_value,
        "creditCost":paid.credit_cost,"createdAt":paid.created_at.isoformat(),"error":
            {"kind":paid.error.get("kind"),"message":"Yêu cầu đã dừng; toàn bộ credit đã được hoàn trả."} if paid.error else None}

@router.get("/formality-requests")
def history(request:Request,db:Db,limit:int=Query(default=100,ge=1,le=200)):
    account=account_for(request,db)
    rows=db.scalars(select(PaidDataRequest).where(PaidDataRequest.account_id==account.id,
        PaidDataRequest.root_department_id==account.root_department_id).order_by(PaidDataRequest.created_at.desc()).limit(limit))
    unread=db.scalar(select(func.count()).select_from(UserNotification).where(UserNotification.account_id==account.id,UserNotification.read_at.is_(None)))
    return {"items":[serialize_request(db,row) for row in rows],"availableCredits":account.credit_balance,"reservedCredits":account.credit_reserved,"unreadNotifications":unread}

@router.post("/notifications/read")
def read_notifications(payload:NotificationRead,request:Request,db:Db):
    account=account_for(request,db)
    db.execute(update(UserNotification).where(UserNotification.account_id==account.id,
        UserNotification.paid_request_id.in_(payload.requestIds),UserNotification.read_at.is_(None)).values(read_at=datetime.now(timezone.utc)))
    db.commit();return {"state":"read"}

@router.get("/formalities")
def library(request:Request,db:Db,period_type:str=Query(pattern="^(month|quarter|year)$"),year:int=Query(ge=2000,le=2200),period_value:int|None=None):
    account=account_for(request,db);valid_period(period_type,year,period_value)
    rows=db.scalars(own_requests(db,account,period_type,year,period_value).where(PaidDataRequest.state=="ready").order_by(PaidDataRequest.created_at.desc()))
    return {"items":[{"id":str(row.formality_id),"code":db.get(Formality,row.formality_id).code,
        "name":db.get(Formality,row.formality_id).name} for row in rows if (snapshot:=db.get(Snapshot,row.snapshot_id)) is not None and snapshot.state=="complete"]}
