"""Daily score history only, independent of paid TTHC collection."""
import uuid
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import inspect
from sqlalchemy.orm import Session
from qd766.periods import PeriodSelection
from .database import get_session
from .daily_history import history_payload
from .models import Department
router=APIRouter(prefix='/api/v1/dashboard')

@router.get('/daily-history')
def daily_history(request:Request,root_department_id:uuid.UUID,unit_id:uuid.UUID,
        period_type:Literal['month','quarter','year'],year:int=Query(ge=2026,le=2100),
        period_value:int|None=Query(default=None,ge=1,le=12),limit:int=Query(default=31,ge=1,le=366),include_peers:bool=False,
        db:Session=Depends(get_session)):
    root=getattr(request.state,'authorized_root_id',None)
    unit=getattr(request.state,'authorized_unit_id',None)
    if root is not None and root!=root_department_id:raise HTTPException(403,'Tỉnh không thuộc phạm vi được phép xem.')
    if unit is not None and unit!=unit_id:raise HTTPException(403,'Cơ quan không thuộc phạm vi được phép xem.')
    try:
        period=PeriodSelection(period_type,year,period_value);period.validate_collectable()
    except ValueError:raise HTTPException(422,'Kỳ báo cáo không hợp lệ.')
    department=db.get(Department,unit_id)
    if department is None:raise HTTPException(404,'Không tìm thấy cơ quan.')
    # Verify membership from captured source tree, never from a browser-supplied ID alone.
    from .models import Entity,Dataset,Snapshot
    from sqlalchemy import select
    if unit_id!=root_department_id and db.scalar(select(Entity.id).join(Dataset).join(Snapshot).where(
            Entity.department_id==unit_id,Snapshot.root_department_id==root_department_id).limit(1)) is None:
        raise HTTPException(403,'Cơ quan không thuộc tỉnh được chọn.')
    if not inspect(db.bind).has_table('daily_observations'):
        return {'days':[],'scope':'all','reportingPolicy':'previous-day-02:00-Asia/Ho_Chi_Minh','available':False}
    payload=history_payload(db,root_department_id,unit_id,period,limit,include_peers)
    if unit is not None:
        for day in payload['days']:
            day['peerScores']={str(unit):day['peerScores'][str(unit)]} if str(unit) in day['peerScores'] else {}
    return payload
