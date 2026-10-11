"""Account-owned preferences only. No scores, credits or collection writes."""
import uuid
from fastapi import APIRouter, Request, Response, HTTPException
from pydantic import BaseModel, Field, ConfigDict
from sqlalchemy import select, inspect
from .auth import current_session, SESSION_COOKIE, csrf_matches
from .models import AgencyWatchPreference, UserAccount, Department
from .admin import units_statement
router=APIRouter(prefix='/api/v1/me/agency-watch')
class WatchUpdate(BaseModel):
    model_config=ConfigDict(extra='forbid')
    provinceId:uuid.UUID
    unitIds:list[uuid.UUID]=Field(max_length=5)
def actor(request,db,root,write=False):
    session,account=current_session(db,request.cookies.get(SESSION_COOKIE))
    if account is None:raise HTTPException(401,'Vui lòng đăng nhập.')
    if not account.trial_admitted:raise HTTPException(403,'Tài khoản chưa được duyệt.')
    if account.role!='admin' and account.access_tier!='national' and root!=account.root_department_id:
        raise HTTPException(403,'Danh sách không thuộc tỉnh được gán.')
    if write and not csrf_matches(request.headers.get('X-QD766-CSRF',''),session.csrf_token):
        raise HTTPException(403,'Xác nhận phiên không hợp lệ.')
    if not inspect(db.connection()).has_table('agency_watch_preferences'):
        raise HTTPException(503,'Chưa nâng schema Theo dõi cơ quan.')
    return account
@router.get('')
def read(request:Request,response:Response,province_id:uuid.UUID):
    response.headers['Cache-Control']='no-store'
    with request.app.state.session_factory() as db:
        account=actor(request,db,province_id)
        row=db.get(AgencyWatchPreference,(account.id,province_id))
        return {'unitIds':row.unit_ids if row else []}
@router.post('')
def save(payload:WatchUpdate,request:Request,response:Response):
    response.headers['Cache-Control']='no-store'
    with request.app.state.session_factory.begin() as db:
        account=actor(request,db,payload.provinceId,True)
        # Serialize first inserts/updates for this account; other accounts do not block.
        db.scalar(select(UserAccount).where(UserAccount.id==account.id).with_for_update())
        if len(set(payload.unitIds))!=len(payload.unitIds):raise HTTPException(422,'Không chọn trùng cơ quan.')
        if payload.unitIds:
            valid={unit.id for unit in db.scalars(units_statement(payload.provinceId).where(Department.id.in_(payload.unitIds)))}
            if not set(payload.unitIds)<=valid or account.unit_department_id in payload.unitIds:
                raise HTTPException(422,'Chỉ chọn cơ quan khác trong cùng tỉnh.')
        ids=[str(value) for value in payload.unitIds]
        row=db.get(AgencyWatchPreference,(account.id,payload.provinceId))
        if row is None:db.add(AgencyWatchPreference(account_id=account.id,root_department_id=payload.provinceId,unit_ids=ids))
        else:row.unit_ids=ids
        db.flush()
        return {'unitIds':ids}
