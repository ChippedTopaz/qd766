"""Trivia scoring is account/round-scoped, server-timed and unrelated to credits."""
import uuid,secrets,json
from datetime import datetime,timedelta,timezone
from typing import Literal
from fastapi import APIRouter, HTTPException, Request, Query
from pydantic import BaseModel, ConfigDict, Field, model_validator, field_validator
from sqlalchemy import select, inspect, func, text
from .auth import current_session, SESSION_COOKIE, csrf_matches
from .admin import administrator, audit
from .models import UserAccount, TriviaQuestion, TriviaProfile, TriviaAnswer, Department
router=APIRouter()

def trivia_gate(db,exclusive=False):
    # Readers/players stay concurrent; deletion waits for in-flight Trivia writes.
    # Always take this gate before account/question row locks to avoid deadlocks.
    if db.bind.dialect.name=='postgresql':
        statement=text('SELECT pg_advisory_xact_lock(7660024)') if exclusive else text('SELECT pg_advisory_xact_lock_shared(7660024)')
        db.execute(statement)

def ready(db):
    inspector=inspect(db.bind)
    return all(inspector.has_table(model.__tablename__) and
        set(model.__table__.columns.keys())<={c['name'] for c in inspector.get_columns(model.__tablename__)}
        for model in (TriviaQuestion,TriviaProfile,TriviaAnswer))

def player(request,db,write=False):
    trivia_gate(db)
    session,account=current_session(db,request.cookies.get(SESSION_COOKIE))
    if account is None:raise HTTPException(401,'Vui lòng đăng nhập.')
    if not account.trial_admitted:raise HTTPException(403,'Tài khoản chưa được duyệt.')
    if write and not csrf_matches(request.headers.get('X-QD766-CSRF',''),session.csrf_token):
        raise HTTPException(403,'Xác nhận phiên không hợp lệ.')
    # Serialize assignment and scoring across tabs/processes in PostgreSQL.
    db.scalar(select(UserAccount).where(UserAccount.id==account.id).with_for_update())
    return account

def stats(profile):
    return {'score':profile.score,'streak':profile.streak,'best':profile.best,'answered':profile.answered}

def profile_for(db,account):
    profile=db.get(TriviaProfile,account.id)
    if profile is None:
        profile=TriviaProfile(account_id=account.id);db.add(profile);db.flush()
    return profile

def public_question(question):
    return {'id':str(question.id),'prompt':question.prompt,'choices':question.choices}

def now_utc():return datetime.now(timezone.utc)

def as_utc(value):
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)

def expired(profile,now):
    return profile.pending_deadline is not None and as_utc(profile.pending_deadline)<=now

def record_answer(db,account,profile,question,choice,timeout=False):
    correct=not timeout and choice==question.correct_index
    profile.score+=int(correct);profile.answered+=1
    profile.streak=profile.streak+1 if correct else 0;profile.best=max(profile.best,profile.streak)
    profile.pending_id=None;profile.pending_deadline=None
    entry=TriviaAnswer(account_id=account.id,question_id=question.id,round_id=profile.round_id,
        choice=choice,correct=correct,timed_out=timeout,score_after=profile.score,
        streak_after=profile.streak,best_after=profile.best,answered_after=profile.answered)
    db.add(entry);db.flush()
    return entry

def current_body(db,account,profile):
    now=now_utc();timed_out=False
    question=db.get(TriviaQuestion,profile.pending_id) if profile.pending_id else None
    if question and question.state=='published' and expired(profile,now):
        record_answer(db,account,profile,question,None,True);question=None;timed_out=True
    if question is None or question.state!='published':
        answered=select(TriviaAnswer.question_id).where(TriviaAnswer.account_id==account.id,TriviaAnswer.round_id==profile.round_id)
        ids=list(db.scalars(select(TriviaQuestion.id).where(TriviaQuestion.state=='published',TriviaQuestion.id.not_in(answered))))
        question=db.get(TriviaQuestion,secrets.choice(ids)) if ids else None
        profile.pending_id=question.id if question else None
        profile.pending_deadline=now+timedelta(seconds=60) if question else None
    return {'available':True,'question':{**public_question(question),'roundId':str(profile.round_id),
        'expiresAt':as_utc(profile.pending_deadline).isoformat()} if question else None,
        'stats':stats(profile),'roundId':str(profile.round_id),'serverNow':now.isoformat(),'timedOut':timed_out}

@router.get('/api/v1/me/trivia')
def current(request:Request):
    with request.app.state.session_factory.begin() as db:
        account=player(request,db)
        if not ready(db):return {'available':False,'question':None}
        profile=profile_for(db,account)
        return current_body(db,account,profile)

@router.get('/api/v1/me/trivia/leaderboard')
def leaderboard(request:Request):
    with request.app.state.session_factory.begin() as db:
        session,account=current_session(db,request.cookies.get(SESSION_COOKIE))
        if account is None:raise HTTPException(401,'Vui lòng đăng nhập.')
        if not account.trial_admitted:raise HTTPException(403,'Tài khoản chưa được duyệt.')
        if not ready(db):raise HTTPException(503,'Hỏi đáp chưa được kích hoạt.')
        trivia_gate(db)
        # Count each surviving question once across all rounds, only if answered
        # correctly at least once. Replays must not inflate the leaderboard.
        counts=select(TriviaAnswer.account_id,func.count(func.distinct(TriviaAnswer.question_id)).label('correct_count')).where(
            TriviaAnswer.correct.is_(True)).group_by(TriviaAnswer.account_id).subquery()
        correct_count=func.coalesce(counts.c.correct_count,0)
        rows=db.execute(select(UserAccount.display_name,Department.name,TriviaProfile.best,correct_count)
            .join(TriviaProfile,TriviaProfile.account_id==UserAccount.id)
            .outerjoin(Department,Department.id==UserAccount.root_department_id)
            .outerjoin(counts,counts.c.account_id==UserAccount.id)
            .where(UserAccount.active.is_(True),UserAccount.trial_admitted.is_(True),TriviaProfile.best>0)
            .order_by(TriviaProfile.best.desc(),correct_count.desc(),UserAccount.display_name,UserAccount.id).limit(20))
        return {'players':[{'rank':index,'name':name,'province':province or 'Chưa cập nhật',
                            'best':best,'correctAnswers':correct}
                           for index,(name,province,best,correct) in enumerate(rows,1)]}

class RestartInput(BaseModel):
    model_config=ConfigDict(extra='forbid')
    roundId:uuid.UUID

@router.post('/api/v1/me/trivia/restart')
def restart(payload:RestartInput,request:Request):
    with request.app.state.session_factory.begin() as db:
        account=player(request,db,True)
        if not ready(db):raise HTTPException(503,'Hỏi - đáp nhanh chưa được kích hoạt.')
        profile=profile_for(db,account)
        if profile.round_id!=payload.roundId:return current_body(db,account,profile)
        current_body(db,account,profile)
        if profile.pending_id is not None:raise HTTPException(409,'Hãy hoàn thành bộ câu hỏi hiện tại trước khi trả lời lại.')
        profile.round_id=uuid.uuid4();profile.score=0;profile.streak=0;profile.answered=0
        return current_body(db,account,profile)

class AnswerInput(BaseModel):
    model_config=ConfigDict(extra='forbid')
    questionId:uuid.UUID
    roundId:uuid.UUID
    choice:int=Field(ge=0,le=5,strict=True)

def answer_result(answer,question):
    return {'correct':answer.correct,'timedOut':answer.timed_out,'correctIndex':question.correct_index,'explanation':question.explanation,
        'stats':{'score':answer.score_after,'streak':answer.streak_after,'best':answer.best_after,'answered':answer.answered_after}}

@router.post('/api/v1/me/trivia/answer')
def answer(payload:AnswerInput,request:Request):
    with request.app.state.session_factory.begin() as db:
        account=player(request,db,True)
        if not ready(db):raise HTTPException(503,'Hỏi - đáp nhanh chưa được kích hoạt.')
        question=db.scalar(select(TriviaQuestion).where(TriviaQuestion.id==payload.questionId).with_for_update())
        profile=profile_for(db,account)
        if profile.round_id!=payload.roundId:raise HTTPException(409,'Lượt chơi đã thay đổi. Hãy tải lại câu hỏi.')
        existing=db.get(TriviaAnswer,(account.id,payload.questionId,payload.roundId))
        if existing:
            # Another tab may have answered later questions since this response.
            # Replaying an old answer must not move the visible totals backwards.
            return {**answer_result(existing,question),'stats':stats(profile_for(db,account))}
        if question is None or profile.pending_id!=question.id or question.state!='published':
            raise HTTPException(409,'Câu hỏi đã thay đổi. Hãy tải lại câu hỏi.')
        if payload.choice>=len(question.choices):raise HTTPException(422,'Đáp án không hợp lệ.')
        timeout=expired(profile,now_utc())
        entry=record_answer(db,account,profile,question,None if timeout else payload.choice,timeout)
        return answer_result(entry,question)

class QuestionInput(BaseModel):
    model_config=ConfigDict(extra='forbid')
    prompt:str=Field(min_length=5,max_length=1000)
    choices:list[str]=Field(min_length=2,max_length=6)
    correctIndex:int=Field(ge=0,le=5,strict=True)
    explanation:str=Field(default='',max_length=2000)
    state:Literal['draft','published','retired']='draft'
    revision:int=Field(default=0,ge=0)
    @model_validator(mode='after')
    def validate_choices(self):
        self.prompt=self.prompt.strip();self.choices=[c.strip() for c in self.choices]
        if len(self.prompt)<5 or any(not c or len(c)>400 for c in self.choices) or len(set(self.choices))!=len(self.choices) or self.correctIndex>=len(self.choices):
            raise ValueError('Câu hỏi và đáp án không hợp lệ hoặc trùng nhau.')
        return self

def admin_question(q):
    return {**public_question(q),'correctIndex':q.correct_index,'explanation':q.explanation,
        'state':q.state,'locked':q.locked,'revision':q.revision}

@router.get('/api/v1/admin/trivia')
def bank(request:Request,q:str=Query('',max_length=200),offset:int=Query(0,ge=0),limit:int=Query(10,ge=1,le=100),state:Literal['draft','published','retired']|None=None):
    with request.app.state.session_factory() as db:
        administrator(request,db)
        if not ready(db):return {'available':False,'questions':[],'total':0}
        predicate=TriviaQuestion.prompt.icontains(q.strip().casefold(),autoescape=True)
        if state is not None:predicate=predicate & (TriviaQuestion.state==state)
        counts=select(TriviaAnswer.question_id,func.count().label('attempts'),
            func.count(func.distinct(TriviaAnswer.account_id)).label('users')).where(TriviaAnswer.correct.is_(True)).group_by(TriviaAnswer.question_id).subquery()
        rows=db.execute(select(TriviaQuestion,counts.c.attempts,counts.c.users).outerjoin(counts,counts.c.question_id==TriviaQuestion.id)
            .where(predicate).order_by(TriviaQuestion.created_at.desc(),TriviaQuestion.id).offset(offset).limit(limit))
        total=db.scalar(select(func.count()).select_from(TriviaQuestion).where(predicate))
        return {'available':True,'total':total,'questions':[{**admin_question(item),'correctAttempts':attempts or 0,'correctUsers':users or 0}
            for item,attempts,users in rows]}

@router.get('/api/v1/admin/trivia/{question_id}/correct-users')
def correct_users(question_id:uuid.UUID,request:Request,offset:int=Query(0,ge=0),limit:int=Query(100,ge=1,le=100)):
    with request.app.state.session_factory() as db:
        administrator(request,db)
        if not ready(db):raise HTTPException(503,'Hỏi - đáp nhanh chưa được kích hoạt.')
        if db.get(TriviaQuestion,question_id) is None:raise HTTPException(404,'Không tìm thấy câu hỏi.')
        predicate=(TriviaAnswer.question_id==question_id,TriviaAnswer.correct.is_(True))
        rows=db.execute(select(UserAccount.id,UserAccount.display_name,UserAccount.email,func.count(),func.max(TriviaAnswer.created_at))
            .join(TriviaAnswer,TriviaAnswer.account_id==UserAccount.id).where(*predicate)
            .group_by(UserAccount.id,UserAccount.display_name,UserAccount.email)
            .order_by(func.max(TriviaAnswer.created_at).desc(),UserAccount.id).offset(offset).limit(limit))
        total=db.scalar(select(func.count(func.distinct(TriviaAnswer.account_id))).where(*predicate))
        return {'total':total,'users':[{'id':str(id),'name':name,'email':email,'correctAttempts':attempts,
            'lastCorrectAt':as_utc(last).isoformat()} for id,name,email,attempts,last in rows]}

def save_question(payload,request,question_id=None):
    with request.app.state.session_factory.begin() as db:
        actor=administrator(request,db,write=True)
        trivia_gate(db)
        if not ready(db):raise HTTPException(503,'Cần nâng schema Trivia trước khi lưu câu hỏi.')
        if question_id:
            q=db.scalar(select(TriviaQuestion).where(TriviaQuestion.id==question_id).with_for_update())
            if q is None:raise HTTPException(404,'Không tìm thấy câu hỏi.')
            if payload.revision!=q.revision:raise HTTPException(409,'Câu hỏi đã được sửa ở nơi khác. Hãy tải lại.')
            if q.locked and (q.prompt!=payload.prompt or q.choices!=payload.choices or q.correct_index!=payload.correctIndex or q.explanation!=payload.explanation):
                raise HTTPException(409,'Câu hỏi đã công khai được khóa nội dung. Hãy tạo câu hỏi mới.')
            if not q.locked and len(payload.choices)>3:
                raise HTTPException(422,'Câu hỏi chỉ được có 2–3 đáp án A–C.')
            q.revision+=1
        else:
            if len(payload.choices)>3:raise HTTPException(422,'Câu hỏi chỉ được có 2–3 đáp án A–C.')
            q=TriviaQuestion();db.add(q)
        q.prompt=payload.prompt;q.choices=payload.choices;q.correct_index=payload.correctIndex
        q.explanation=payload.explanation;q.state=payload.state
        q.locked=bool(q.locked) or payload.state=='published'
        db.flush();audit(db,actor,'trivia_question_saved',questionId=str(q.id),state=q.state,revision=q.revision)
        return admin_question(q)

@router.post('/api/v1/admin/trivia')
def create_question(payload:QuestionInput,request:Request):return save_question(payload,request)

@router.post('/api/v1/admin/trivia/import')
async def import_questions(request:Request):
    from .trivia_import import read_questions,question_key
    with request.app.state.session_factory.begin() as db:
        actor=administrator(request,db,write=True)
        if not ready(db):raise HTTPException(503,'Cần nâng schema Trivia trước khi nhập câu hỏi.')
        # Bound streamed JSON before decoding, including requests without Content-Length.
        raw=bytearray()
        async for chunk in request.stream():
            if len(raw)+len(chunk)>3*1024*1024:raise HTTPException(413,'File Excel tối đa 2 MB.')
            raw.extend(chunk)
        try:
            payload=json.loads(raw)
            if not isinstance(payload,dict) or set(payload)!={'file','confirm'} or not isinstance(payload['file'],str) or type(payload['confirm']) is not bool:
                raise ValueError('Yêu cầu nhập không hợp lệ.')
            questions,errors=read_questions(payload['file'],QuestionInput)
        except (ValueError,TypeError) as error:raise HTTPException(422,str(error)) from None
        # Serialize bank imports across administrators/processes on PostgreSQL.
        trivia_gate(db)
        if payload['confirm'] and db.bind.dialect.name=='postgresql':
            db.execute(text('SELECT pg_advisory_xact_lock(7660023)'))
        existing={question_key(prompt) for prompt in db.scalars(select(TriviaQuestion.prompt))}
        seen=set();duplicates=[];new=[]
        for row,q in questions:
            key=question_key(q.prompt)
            if key in existing or key in seen:duplicates.append({'row':row,'prompt':q.prompt})
            else:new.append((row,q));seen.add(key)
        result={'valid':not errors,'errors':errors,'duplicates':duplicates,'newCount':len(new),
            'questions':[{'row':row,**q.model_dump()} for row,q in new],'saved':0}
        if payload['confirm']:
            if errors:raise HTTPException(422,'File có dòng lỗi. Chưa lưu bất kỳ câu hỏi nào; hãy sửa file và kiểm tra lại.')
            for _,q in new:
                db.add(TriviaQuestion(prompt=q.prompt,choices=q.choices,correct_index=q.correctIndex,explanation=q.explanation,state='draft',locked=False))
            db.flush();audit(db,actor,'trivia_questions_imported',count=len(new),duplicates=len(duplicates))
            result['saved']=len(new)
        return result

@router.post('/api/v1/admin/trivia/{question_id}')
def update_question(question_id:uuid.UUID,payload:QuestionInput,request:Request):return save_question(payload,request,question_id)

class PublishQuestionInput(BaseModel):
    model_config=ConfigDict(extra='forbid')
    revision:int=Field(ge=1,strict=True)

@router.post('/api/v1/admin/trivia/{question_id}/publish')
def publish_question(question_id:uuid.UUID,payload:PublishQuestionInput,request:Request):
    with request.app.state.session_factory.begin() as db:
        actor=administrator(request,db,write=True)
        trivia_gate(db)
        if not ready(db):raise HTTPException(503,'Hỏi - đáp nhanh chưa được kích hoạt.')
        q=db.scalar(select(TriviaQuestion).where(TriviaQuestion.id==question_id).with_for_update())
        if q is None:raise HTTPException(404,'Không tìm thấy câu hỏi.')
        if q.revision!=payload.revision:raise HTTPException(409,'Câu hỏi đã thay đổi. Hãy tải lại trước khi duyệt.')
        if q.state!='draft':raise HTTPException(409,'Chỉ duyệt công khai câu đang là Nháp.')
        if len(q.choices)>3:raise HTTPException(422,'Hãy sửa bản nháp còn tối đa 3 đáp án trước khi duyệt.')
        q.state='published';q.locked=True;q.revision+=1
        db.flush();audit(db,actor,'trivia_question_published',questionId=str(q.id),revision=q.revision)
        return admin_question(q)

class DeleteQuestionInput(BaseModel):
    model_config=ConfigDict(extra='forbid')
    revision:int=Field(ge=1,strict=True)
    confirm:Literal[True]
    @field_validator('confirm',mode='before')
    @classmethod
    def explicit_confirmation(cls,value):
        if value is not True:raise ValueError('Cần xác nhận xóa vĩnh viễn.')
        return value

def recount_after_deletion(db,profile):
    """Remove correct contributions without erasing historical wrong/timeout breaks."""
    answers=list(db.scalars(select(TriviaAnswer).where(TriviaAnswer.account_id==profile.account_id)
        .order_by(TriviaAnswer.round_id,TriviaAnswer.answered_after)))
    rounds={};best=0
    for answer in answers:
        score,streak,answered=rounds.get(answer.round_id,(0,0,0))
        # Original segment starts preserve a break even if its failed question was deleted.
        if not answer.correct or answer.streak_after==1:streak=0
        score+=int(answer.correct);streak=streak+1 if answer.correct else 0;answered+=1
        rounds[answer.round_id]=(score,streak,answered);best=max(best,streak)
        answer.score_after=score;answer.streak_after=streak;answer.answered_after=answered
    profile.score,tail,profile.answered=rounds.get(profile.round_id,(0,0,0))
    # Deleting an incorrect last answer must not revive an already broken streak.
    profile.streak=min(profile.streak,tail);profile.best=best
    for answer in answers:answer.best_after=min(answer.best_after,best)

@router.post('/api/v1/admin/trivia/{question_id}/delete')
def delete_question(question_id:uuid.UUID,payload:DeleteQuestionInput,request:Request):
    with request.app.state.session_factory.begin() as db:
        actor=administrator(request,db,write=True)
        if not ready(db):raise HTTPException(503,'Hỏi - đáp nhanh chưa được kích hoạt.')
        trivia_gate(db,True)
        question=db.scalar(select(TriviaQuestion).where(TriviaQuestion.id==question_id).with_for_update())
        if question is None:raise HTTPException(404,'Câu hỏi đã bị xóa hoặc không tồn tại.')
        if question.revision!=payload.revision:raise HTTPException(409,'Câu hỏi đã thay đổi. Hãy tải lại trước khi xóa.')
        affected=set(db.scalars(select(TriviaAnswer.account_id).where(TriviaAnswer.question_id==question_id)))
        pending=list(db.scalars(select(TriviaProfile).where(TriviaProfile.pending_id==question_id)))
        for profile in pending:profile.pending_id=None;profile.pending_deadline=None
        from sqlalchemy import delete
        deleted=db.execute(delete(TriviaAnswer).where(TriviaAnswer.question_id==question_id)).rowcount
        db.flush()
        for account_id in affected:
            profile=db.get(TriviaProfile,account_id)
            if profile is not None:recount_after_deletion(db,profile)
        db.delete(question);db.flush()
        audit(db,actor,'trivia_question_deleted',questionId=str(question_id),deletedAnswers=deleted,affectedAccounts=len(affected),clearedPending=len(pending))
        return {'deleted':True,'deletedAnswers':deleted,'affectedAccounts':len(affected)}
