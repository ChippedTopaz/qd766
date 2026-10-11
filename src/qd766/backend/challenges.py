"""Consensual, same-province score challenges. Never touches credits or collection."""
import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
from zoneinfo import ZoneInfo
from typing import Literal
from fastapi import APIRouter, Request, HTTPException, Response, Query
from pydantic import BaseModel, Field, ConfigDict
from sqlalchemy import select, inspect, text, or_, and_, func, case, union_all
from sqlalchemy.exc import IntegrityError
from qd766.periods import PeriodSelection, ENDPOINTS
from .auth import current_session, SESSION_COOKIE, csrf_matches
from .models import AgencyChallenge, UserAccount, Department, Snapshot

router=APIRouter(prefix='/api/v1/me/challenges')
VIETNAM=ZoneInfo('Asia/Ho_Chi_Minh')

def now_utc():
    return datetime.now(timezone.utc)

def utc(value):
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)

def period_end(kind,year,value):
    return date.fromisoformat(PeriodSelection(kind,year,value if kind!='year' else None).date_range()[1])

def ended(k,now=None):
    return period_end(k.period_type,k.year,k.period_key)<(now or now_utc()).astimezone(VIETNAM).date()

def ready(db):
    return inspect(db.connection()).has_table('agency_challenges')

def actor(request,db,write=False):
    session,account=current_session(db,request.cookies.get(SESSION_COOKIE))
    if not account:raise HTTPException(401,'Vui lòng đăng nhập.')
    if not account.trial_admitted:raise HTTPException(403,'Tài khoản chưa được duyệt.')
    if write:
        if not csrf_matches(request.headers.get('X-QD766-CSRF',''),session.csrf_token):
            raise HTTPException(403,'Xác nhận phiên không hợp lệ.')
        # Both request and acceptance take the same gate before rows. Limits and
        # duplicate/reverse requests remain atomic across processes.
        if db.bind.dialect.name=='postgresql':
            db.execute(text('SELECT pg_advisory_xact_lock(7660026)'))
    if not ready(db):raise HTTPException(503,'Chưa nâng schema Thách đấu.')
    return account

def eligible(account):
    return account.active and account.trial_admitted and account.access_tier=='agency' and account.unit_department_id and account.root_department_id

def opponents(db,account_id):
    values=set()
    for k in db.scalars(select(AgencyChallenge).where(
            or_(AgencyChallenge.sender_id==account_id,AgencyChallenge.recipient_id==account_id),
            AgencyChallenge.state.in_(['pending','accepted']))):
        if k.state=='pending' and ended(k):continue
        values.add(k.recipient_id if k.sender_id==account_id else k.sender_id)
    return values

class CreateChallenge(BaseModel):
    model_config=ConfigDict(extra='forbid')
    recipientId: uuid.UUID
    periodType: Literal['month','quarter','year']
    year: int=Field(ge=2000,le=9998)
    periodValue: int | None=None

class AnswerChallenge(BaseModel):
    model_config=ConfigDict(extra='forbid')
    action: Literal['accept','decline']

def public_row(db,k,viewer):
    sender=db.get(UserAccount,k.sender_id);recipient=db.get(UserAccount,k.recipient_id)
    unit_a=db.get(Department,k.sender_unit_id);unit_b=db.get(Department,k.recipient_unit_id)
    state='expired' if k.state=='pending' and ended(k) else 'waiting-result' if k.state=='accepted' and ended(k) else k.state
    winner=None
    if k.state=='finished' and k.sender_score!=k.recipient_score:
        winner=str(k.sender_id if k.sender_score>k.recipient_score else k.recipient_id)
    return dict(id=str(k.id),senderId=str(k.sender_id),recipientId=str(k.recipient_id),
        sender=sender.display_name,recipient=recipient.display_name,
        senderUnit=unit_a.name,recipientUnit=unit_b.name,periodType=k.period_type,
        year=k.year,periodValue=k.period_key or None,state=state,
        senderScore=float(k.sender_score) if k.sender_score is not None else None,
        recipientScore=float(k.recipient_score) if k.recipient_score is not None else None,
        winnerId=winner,canAnswer=k.recipient_id==viewer.id and state=='pending',
        createdAt=utc(k.created_at).isoformat())

def public_rows(db,items,viewer):
    items=list(items)
    if not items:return []
    # Keep strong references so the ORM identity map serves all row lookups.
    people=list(db.scalars(select(UserAccount).where(UserAccount.id.in_(
        {uid for k in items for uid in (k.sender_id,k.recipient_id)}))))
    units=list(db.scalars(select(Department).where(Department.id.in_(
        {uid for k in items for uid in (k.sender_unit_id,k.recipient_unit_id)}))))
    return [public_row(db,k,viewer) for k in items]

@router.get('/directory')
def directory(request:Request,response:Response):
    response.headers['Cache-Control']='no-store'
    with request.app.state.session_factory() as db:
        account=actor(request,db)
        if not eligible(account):return {'eligible':False,'agencies':[]}
        grouped={}
        others=list(db.scalars(select(UserAccount).where(UserAccount.active.is_(True),
                UserAccount.trial_admitted.is_(True),UserAccount.access_tier=='agency',
                UserAccount.root_department_id==account.root_department_id,
                UserAccount.unit_department_id!=account.unit_department_id).order_by(UserAccount.display_name)))
        units={u.id:u for u in db.scalars(select(Department).where(Department.id.in_({a.unit_department_id for a in others})))}
        for other in others:
            unit=units.get(other.unit_department_id)
            if not unit:continue
            entry=grouped.setdefault(str(unit.id),{'id':str(unit.id),'name':unit.name,'users':[]})
            # Public name and opaque ID only. No email/birthday/profile/credits.
            entry['users'].append({'id':str(other.id),'name':other.display_name})
        return {'eligible':True,'agencies':list(grouped.values())}

@router.get('/incoming')
def incoming(request:Request,response:Response):
    response.headers['Cache-Control']='no-store'
    with request.app.state.session_factory() as db:
        account=actor(request,db)
        today=now_utc().astimezone(VIETNAM).date()
        query=select(AgencyChallenge).where(AgencyChallenge.recipient_id==account.id,AgencyChallenge.state=='pending',
            or_(AgencyChallenge.year>today.year,and_(AgencyChallenge.year==today.year,or_(
                AgencyChallenge.period_type=='year',
                and_(AgencyChallenge.period_type=='month',AgencyChallenge.period_key>=today.month),
                and_(AgencyChallenge.period_type=='quarter',AgencyChallenge.period_key>=(today.month+2)//3)))))
        count=db.scalar(select(func.count()).select_from(query.subquery()))
        entries=db.scalars(query.order_by(AgencyChallenge.created_at.desc()).limit(20))
        return {'count':count,'items':public_rows(db,entries,account)}

@router.post('')
def create(payload:CreateChallenge,request:Request):
    with request.app.state.session_factory.begin() as db:
        account=actor(request,db,True);other=db.get(UserAccount,payload.recipientId)
        if not eligible(account) or not other or not eligible(other):
            raise HTTPException(403,'Chỉ tài khoản cơ quan đã được duyệt mới được thách đấu.')
        if other.root_department_id!=account.root_department_id or other.unit_department_id==account.unit_department_id:
            raise HTTPException(403,'Chọn người thuộc cơ quan khác trong cùng tỉnh.')
        try:end=period_end(payload.periodType,payload.year,payload.periodValue)
        except (ValueError,TypeError):raise HTTPException(422,'Kỳ báo cáo không hợp lệ.')
        if payload.periodType=='year' and payload.periodValue is not None:
            raise HTTPException(422,'Kỳ năm không có tháng hoặc quý.')
        if end<now_utc().astimezone(VIETNAM).date():
            raise HTTPException(422,'Chọn kỳ báo cáo chưa kết thúc.')
        pair=':'.join(sorted([str(account.id),str(other.id)]))
        value=payload.periodValue or 0
        if db.scalar(select(AgencyChallenge.id).where(AgencyChallenge.pair_key==pair,
                AgencyChallenge.period_type==payload.periodType,AgencyChallenge.year==payload.year,
                AgencyChallenge.period_key==value)):
            raise HTTPException(409,'Đã có kèo thách đấu giữa hai tài khoản trong kỳ báo cáo chưa kết thúc này.')
        for a,b in [(account,other),(other,account)]:
            existing=opponents(db,a.id)
            if b.id not in existing and len(existing)>=5:
                raise HTTPException(409,'Một trong hai người đã có đủ 5 đối thủ đang chờ hoặc đang thách đấu.')
        k=AgencyChallenge(sender_id=account.id,recipient_id=other.id,pair_key=pair,
            root_department_id=account.root_department_id,sender_unit_id=account.unit_department_id,
            recipient_unit_id=other.unit_department_id,period_type=payload.periodType,
            year=payload.year,period_key=value,state='pending')
        db.add(k)
        try:db.flush()
        except IntegrityError:raise HTTPException(409,'Đã có kèo thách đấu giữa hai tài khoản trong kỳ báo cáo chưa kết thúc này.')
        return public_row(db,k,account)

@router.post('/{challenge_id}/answer')
def answer(challenge_id:uuid.UUID,payload:AnswerChallenge,request:Request):
    with request.app.state.session_factory.begin() as db:
        account=actor(request,db,True)
        k=db.scalar(select(AgencyChallenge).where(AgencyChallenge.id==challenge_id).with_for_update())
        if not k or k.recipient_id!=account.id:raise HTTPException(404,'Không tìm thấy lời thách đấu của bạn.')
        if k.state!='pending' or ended(k):raise HTTPException(409,'Lời thách đấu không còn chờ xác nhận.')
        sender=db.get(UserAccount,k.sender_id)
        if not eligible(account) or not sender or not eligible(sender) or (
                account.unit_department_id!=k.recipient_unit_id or sender.unit_department_id!=k.sender_unit_id
                or account.root_department_id!=k.root_department_id or sender.root_department_id!=k.root_department_id):
            raise HTTPException(403,'Phân quyền cơ quan đã thay đổi; không thể nhận thách đấu này.')
        if payload.action=='accept':
            for a,b in [(account,sender),(sender,account)]:
                if len(opponents(db,a.id))>5:raise HTTPException(409,'Đã vượt giới hạn 5 đối thủ.')
            k.state='accepted';k.accepted_at=now_utc()
        else:k.state='declined'
        db.flush();return public_row(db,k,account)

@router.get('')
def listing(request:Request,response:Response,page:int=Query(1,ge=1)):
    response.headers['Cache-Control']='no-store'
    with request.app.state.session_factory() as db:
        account=actor(request,db)
        # Only own requests; no email directory or cross-province query option.
        query=select(AgencyChallenge).where(or_(AgencyChallenge.sender_id==account.id,
            AgencyChallenge.recipient_id==account.id))
        return challenge_page(db,query,account,page)

def challenge_page(db,query,account,page):
    total=db.scalar(select(func.count()).select_from(query.subquery())) or 0
    page=min(page,max(1,(total+9)//10))
    items=db.scalars(query.order_by(AgencyChallenge.created_at.desc(),AgencyChallenge.id.desc()).offset((page-1)*10).limit(10))
    return {'items':public_rows(db,items,account),'total':total,'page':page,'pageSize':10}

@router.get('/board')
def board(request:Request,response:Response,page:int=Query(1,ge=1),status:Literal['active','finished','top']|None=None):
    response.headers['Cache-Control']='no-store'
    with request.app.state.session_factory() as db:
        account=actor(request,db)
        # Minimal public duel/score information for admitted users, within province.
        if not account.root_department_id:return {'items':[],'players':[],'total':0,'page':1,'pageSize':10}
        if status in ('active','finished'):
            query=select(AgencyChallenge).where(AgencyChallenge.root_department_id==account.root_department_id,
                AgencyChallenge.state==('accepted' if status=='active' else 'finished'))
            return {**challenge_page(db,query,account,page),'players':[]}
        sides=[]
        for aid,a,b in [(AgencyChallenge.sender_id,AgencyChallenge.sender_score,AgencyChallenge.recipient_score),
                        (AgencyChallenge.recipient_id,AgencyChallenge.recipient_score,AgencyChallenge.sender_score)]:
            sides.append(select(aid.label('aid'),case((a>b,3),(a==b,1),else_=0).label('points'),
                case((a>b,1),else_=0).label('wins'),case((a==b,1),else_=0).label('draws'),
                case((a<b,1),else_=0).label('losses')).where(
                AgencyChallenge.root_department_id==account.root_department_id,AgencyChallenge.state=='finished'))
        results=union_all(*sides).subquery()
        points=func.sum(results.c.points).label('points');wins=func.sum(results.c.wins).label('wins')
        ranking=select(UserAccount.display_name,points,wins,func.sum(results.c.draws),func.sum(results.c.losses)).join(
            results,results.c.aid==UserAccount.id).where(UserAccount.active.is_(True),UserAccount.trial_admitted.is_(True)).group_by(
            UserAccount.id,UserAccount.display_name).order_by(points.desc(),wins.desc(),UserAccount.id).limit(20)
        players=[{'rank':i+1,'name':name,'points':p,'wins':w,'draws':d,'losses':l}
                 for i,(name,p,w,d,l) in enumerate(db.execute(ranking))]
        if status=='top':return {'items':[],'players':players}
        query=select(AgencyChallenge).where(AgencyChallenge.root_department_id==account.root_department_id,
            AgencyChallenge.state.in_(['accepted','finished']))
        return {**challenge_page(db,query,account,page),'players':players}

def settle_snapshot(db,snapshot,*,collected_at=None,collection_job_id=None):
    """First complete post-period source snapshot shared by both agencies wins.
    Invoked only in the collection write transaction. GET requests never settle.
    Results are immutable and retain the exact source snapshot for audit.
    """
    if not isinstance(snapshot,Snapshot) or not ready(db) or snapshot.scope!='all' or snapshot.state!='complete':return 0
    end=period_end(snapshot.period_type,snapshot.year,snapshot.period_value)
    if end>=now_utc().astimezone(VIETNAM).date():return 0
    if utc(collected_at or snapshot.created_at).astimezone(VIETNAM).date()<=end:return 0
    count=0
    for k in db.scalars(select(AgencyChallenge).where(AgencyChallenge.state=='accepted',
            AgencyChallenge.root_department_id==snapshot.root_department_id,
            AgencyChallenge.period_type==snapshot.period_type,AgencyChallenge.year==snapshot.year,
            AgencyChallenge.period_key==(snapshot.period_value or 0)).with_for_update()):
        def total(unit_id):
            points={}
            for dataset in snapshot.datasets:
                if dataset.group_name not in ENDPOINTS:continue
                entity=next((e for e in dataset.entities if e.department_id==unit_id),None)
                if entity and entity.api_score is not None and entity.api_max_score is not None:
                    score=Decimal(str(entity.api_score));maximum=Decimal(str(entity.api_max_score))
                    if score.is_finite() and maximum.is_finite() and 0<=score<=maximum:
                        points[dataset.group_name]=(score,maximum)
            if len(points)!=6 or sum(v[1] for v in points.values())!=100:return None
            return sum(v[0] for v in points.values()).quantize(Decimal('.01'),rounding=ROUND_HALF_UP)
        a,b=total(k.sender_unit_id),total(k.recipient_unit_id)
        if a is None or b is None:continue
        k.sender_score=a;k.recipient_score=b;k.result_snapshot_id=snapshot.id
        k.result_collection_job_id=collection_job_id
        k.state='finished';k.finished_at=now_utc();count+=1
    return count
