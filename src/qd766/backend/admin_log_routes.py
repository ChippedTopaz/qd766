"""Read-only, admin-only compact log hub. Existing write/retry/task APIs unchanged."""
from datetime import date
from typing import Literal
from fastapi import APIRouter, Request, Query
from sqlalchemy import select, func
from .admin import administrator
from .admin_log_history import today_report, daily_page, daily_detail, paging
from .collection_monitor import probe_status, stamp
from .models import ProvinceCollectionBatch

router = APIRouter(prefix='/api/v1/admin/logs', tags=['admin log hub'])


@router.get('/recaptures')
def recaptures(request: Request, page: int = Query(1, ge=1, le=100000),
               fromDate: date | None = None, toDate: date | None = None,
               state: Literal['RUNNING','WAITING_FOR_COLLECTOR','AWAITING_ADMIN_REVIEW','PUBLISHED','HALTED','INTERRUPTED','INCOMPLETE','BOUNDED_CHECK_COMPLETE','NEEDS_CHECK','UNREADABLE'] | None = None):
    with request.app.state.session_factory() as db:
        administrator(request, db)
        from .recapture_log import recapture_page
        return recapture_page(page, fromDate, toDate, state)


@router.get('/recaptures/{run_day}')
def recapture(run_day: date, request: Request, page: int = Query(1, ge=1, le=100000),
              state: Literal['SUCCESS','RUNNING','FAILED','HALTED','issues'] | None = None):
    with request.app.state.session_factory() as db:
        administrator(request, db)
        from .recapture_log import recapture_detail
        return recapture_detail(run_day, page, state)


@router.get('/today')
def today(request: Request):
    with request.app.state.session_factory() as db:
        administrator(request, db)
        return today_report(db)


@router.get('/daily')
def history(request: Request, page: int = Query(1, ge=1, le=100000),
            fromDate: date | None = None, toDate: date | None = None,
            state: Literal['COMPLETE','RUNNING','INCOMPLETE','HALTED','FAILED','NOT_STARTED','UNREADABLE','NEEDS_CHECK'] | None = None,
            issuesOnly: bool = False):
    with request.app.state.session_factory() as db:
        administrator(request, db)
        return daily_page(db, page, fromDate, toDate, state, issuesOnly)


@router.get('/daily/{report_day}')
def detail(report_day: date, request: Request, page: int = Query(1, ge=1, le=100000),
           state: Literal['SUCCESS','RUNNING','RETRYING','FAILED','HALTED','issues'] | None = None):
    with request.app.state.session_factory() as db:
        administrator(request, db)
        return daily_detail(db, report_day, page, state)


@router.get('/archive')
def archive(request: Request, kind: Literal['batches','probe'], page: int = Query(1, ge=1, le=100000)):
    with request.app.state.session_factory() as db:
        administrator(request, db)
        if kind == 'probe':
            return {'probe': probe_status(getattr(request.app.state, 'collection_probe_checkpoint', None))}
        total = db.scalar(select(func.count()).select_from(ProvinceCollectionBatch))
        page, offset = paging(page, total)
        rows = db.scalars(select(ProvinceCollectionBatch).order_by(ProvinceCollectionBatch.created_at.desc(), ProvinceCollectionBatch.id.desc()).offset(offset).limit(10))
        return {'items': [{'id': str(b.id), 'state': b.state, 'total': b.total_items,
            'completed': b.completed_items, 'skipped': b.available_items, 'failed': b.failed_items,
            'period': {'type': b.period_type, 'year': b.year, b.period_type: b.period_value},
            'updatedAt': stamp(b.updated_at)} for b in rows], 'total': total, 'page': page, 'pageSize': 10}
