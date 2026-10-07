"""Database-backed FIFO admission; two session-locked provider slots globally.

Only confirmed jobs are consumed. Never hold a DB transaction during HTTP.
PostgreSQL advisory session locks survive transaction commits, not process death.
"""
import asyncio
import logging
import uuid
from contextlib import contextmanager
from dataclasses import replace
from datetime import datetime,timedelta,timezone
from threading import RLock,BoundedSemaphore
import httpx
from fastapi import HTTPException
from sqlalchemy import select,func,text,inspect
from .models import GeminiAnalysis,AnalysisQueueEntry,UserAccount
from .paid_requests import _locked_account
from .credit_wallet import finish,utc
from .wallet_access import active_subscription
from .analysis_rules import VERSION
from . import gemini_client

WAITING_LIMIT=20
WAIT_MINUTES=10
LEASE_MINUTES=10
_COORDINATOR=7661900
_SLOT_BASE=7661910
_LOCAL_LOCK=RLock()
_LOCAL_SLOTS=BoundedSemaphore(2)
logger=logging.getLogger('uvicorn.error')


def verify_schema(engine):
    inspector=inspect(engine)
    columns={c['name'] for c in inspector.get_columns('analysis_queue_entries')}
    if not set(AnalysisQueueEntry.__table__.columns.keys())<=columns:
        raise ValueError('Analysis queue migration required')
    constraints=inspector.get_check_constraints('gemini_analyses')
    if not any(c['name']=='ck_gemini_analysis_state' and 'queued' in c['sqltext']
               and 'cancelled' in c['sqltext'] for c in constraints):
        raise ValueError('Analysis queue states not migrated')


@contextmanager
def admission_lock(db):
    if db.bind.dialect.name=='postgresql':
        db.execute(text('SELECT pg_advisory_xact_lock(:key)'),{'key':_COORDINATOR})
        yield
    else:
        with _LOCAL_LOCK:yield


def check_capacity(db):
    count=db.scalar(select(func.count()).select_from(GeminiAnalysis).where(GeminiAnalysis.state=='queued'))
    if count>=WAITING_LIMIT:
        raise HTTPException(429,'Hàng chờ phân tích đã đầy. Vui lòng thử lại sau; chưa giữ Credit.')


def recover_account(db,account_id,now):
    # Caller locks account first, matching settlement/cancellation lock order.
    rows=db.execute(select(GeminiAnalysis,AnalysisQueueEntry).join(AnalysisQueueEntry).where(
        GeminiAnalysis.account_id==account_id,GeminiAnalysis.state.in_(['queued','running']))).all()
    for row,entry in rows:
        expired=(row.state=='queued' and utc(entry.expires_at)<=now) or (
            row.state=='running' and entry.lease_until is not None and utc(entry.lease_until)<=now)
        if expired:
            finish(db,account_id,request_key='analysis:'+str(row.id),outcome='refund',now=now)
            row.state='failed';row.finished_at=now


def recover_all(factory,now):
    with factory() as db:
        ids=list(db.scalars(select(GeminiAnalysis.account_id).join(AnalysisQueueEntry).where(
            GeminiAnalysis.state.in_(['queued','running'])).distinct()))
    for aid in ids:
        with factory.begin() as db:
            _locked_account(db,aid);recover_account(db,aid,now)


@contextmanager
def provider_slot(engine):
    if engine.dialect.name!='postgresql':
        acquired=_LOCAL_SLOTS.acquire(blocking=False)
        try:yield acquired
        finally:
            if acquired:_LOCAL_SLOTS.release()
        return
    with engine.connect() as connection:
        slot=None
        try:
            for index in range(2):
                key=_SLOT_BASE+index
                if connection.scalar(text('SELECT pg_try_advisory_lock(:key)'),{'key':key}):
                    slot=key;break
            connection.commit()  # Session lock remains; no open transaction during HTTP.
            yield slot is not None
        finally:
            if slot is not None:
                connection.execute(text('SELECT pg_advisory_unlock(:key)'),{'key':slot})
                connection.commit()


def run_one(factory,settings,*,clock=None,generate=None):
    clock=clock or (lambda:datetime.now(timezone.utc))
    generate=generate or gemini_client.generate
    if not settings.gemini_analysis_enabled or not settings.gemini_queue_enabled:return None
    recover_all(factory,clock())
    if settings.wallet_requests_paused:return None
    with provider_slot(factory.kw['bind']) as available:
        if not available:return None
        job=None
        with factory() as db:
            with admission_lock(db):
                from .analysis_feature import feature_state
                maintenance=not feature_state(db)['enabled']
                # Fixed FIFO order for all workers; claim and running limit atomically.
                if db.scalar(select(func.count()).select_from(GeminiAnalysis).where(GeminiAnalysis.state=='running'))>=2:
                    db.rollback();return None
                row=db.scalar(select(GeminiAnalysis).where(GeminiAnalysis.state=='queued').order_by(
                    GeminiAnalysis.created_at,GeminiAnalysis.id).limit(1))
                if row is None:db.rollback();return None
                _locked_account(db,row.account_id)
                entry=db.get(AnalysisQueueEntry,row.id);now=clock()
                # Cancellation/recovery may have completed while we waited for account lock.
                db.refresh(row)
                if row.state!='queued':db.rollback();return None
                account=db.get(UserAccount,row.account_id)
                permitted=account is not None and account.active and account.trial_admitted
                context=row.context
                if permitted and account.role!='admin' and account.access_tier!='national':
                    permitted=str(account.root_department_id)==context['rootDepartmentId']
                    if account.access_tier=='agency':permitted=permitted and str(account.unit_department_id)==context['unitId']
                if (maintenance or entry is None or utc(entry.expires_at)<=now or not permitted or
                        not active_subscription(db,row.account_id,now=now)):
                    finish(db,row.account_id,request_key='analysis:'+str(row.id),outcome='refund',now=now)
                    row.state='failed';row.finished_at=now;db.commit();return 'refunded'
                entry.started_at=now;entry.lease_until=now+timedelta(minutes=LEASE_MINUTES)
                entry.worker_token=uuid.uuid4();row.state='running'
                job=(row.id,row.account_id,entry.worker_token,row.evidence,row.model)
                db.commit()
        job_id,account_id,worker_token,evidence,model=job
        try:
            cards=generate(replace(settings,gemini_model=model),evidence)
        except Exception as error:
            status=error.response.status_code if isinstance(error,httpx.HTTPStatusError) else None
            logger.warning('GEMINI_ANALYSIS_FAILED id=%s type=%s http_status=%s',job_id,type(error).__name__,status)
            cards=None
        with factory.begin() as db:
            _locked_account(db,account_id)
            row=db.get(GeminiAnalysis,job_id);entry=db.get(AnalysisQueueEntry,job_id)
            if row.state!='running' or entry.worker_token!=worker_token:return 'discarded'
            now=clock()
            if cards is None or utc(entry.lease_until)<=now:
                finish(db,account_id,request_key='analysis:'+str(job_id),outcome='refund',now=now)
                row.state='failed'
            else:
                row.result={'cards':cards,'limitations':evidence['limitations'],'version':VERSION,'model':model,
                    'configurationVersion':evidence.get('analysisConfiguration',{}).get('version',0)}
                finish(db,account_id,request_key='analysis:'+str(job_id),outcome='charge',now=now)
                row.state='ready'
            row.finished_at=now
            return row.state


async def worker_loop(factory,settings,stop):
    while not stop.is_set():
        try:
            outcome=await asyncio.to_thread(run_one,factory,settings)
        except Exception as error:
            logger.warning('ANALYSIS_QUEUE_WORKER_FAILED type=%s',type(error).__name__)
            outcome=None
        try:await asyncio.wait_for(stop.wait(),timeout=1 if outcome else 3)
        except TimeoutError:pass
