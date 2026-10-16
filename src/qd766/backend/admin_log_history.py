"""Bounded, SELECT-only log views. Never starts a task, retries a job or changes Credit."""
import json
import sqlite3
import uuid
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from functools import lru_cache
from contextlib import closing
from pathlib import Path

from fastapi import HTTPException
from sqlalchemy import select, func
from .daily_history import FIRST_VALID_REPORT_DATE
from .models import CollectionControl, Department, SourceMonitorAlert, SourceMonitorRun
from .province_refresh import VIETNAM
from .source_monitor import ready

DAILY_ROOT = Path(__file__).resolve().parents[3] / 'data/daily-collection'
PAGE_SIZE = 10


def date_bounds(start, end):
    if end and end.year >= 9999:
        raise HTTPException(422, 'Khoảng ngày không hợp lệ.')
    if start and end and start > end:
        raise HTTPException(422, 'Ngày bắt đầu phải trước hoặc bằng ngày kết thúc.')
    lower = datetime.combine(start, datetime.min.time(), VIETNAM).astimezone(timezone.utc) if start else None
    upper = datetime.combine(end + timedelta(days=1), datetime.min.time(), VIETNAM).astimezone(timezone.utc) if end else None
    return lower, upper


def paging(page, total):
    page = min(page, max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE))
    return page, (page - 1) * PAGE_SIZE


@lru_cache(maxsize=256)
def _checkpoint(path, modified_ns, size):
    # Cache immutable summaries; callers must copy before enriching them.
    if size > 8 * 1024 * 1024:
        raise ValueError('Oversized checkpoint')
    with closing(sqlite3.connect(Path(path).as_uri() + '?mode=ro', uri=True, timeout=1)) as cp:
        rows = cp.execute('SELECT block_key,state,details FROM blocks LIMIT 5001').fetchall()
    if len(rows) > 5000:
        raise ValueError('Oversized checkpoint')
    status = next(((s, json.loads(raw)) for k, s, raw in rows if k == 'run-status'), ('RUNNING', {}))
    blocks = []
    for key, state, raw in rows:
        if key == 'run-status':
            continue
        info = json.loads(raw)
        parts = key.split(':')
        blocks.append({'key': key, 'state': state, 'province': info.get('province'),
            'rootId': parts[-1] if parts[-1] != 'national' else None,
            'period': parts[-2] if len(parts) >= 4 else 'unknown',
            'national': parts[-1] == 'national', 'error': info.get('error'),
            'reason': info.get('reason'), 'retryAttempt': info.get('retryAttempt')})
    detail = [b for b in blocks if not b['national']]
    expected = status[1].get('expected', 102)
    completed = sum(b['state'] == 'SUCCESS' for b in detail)
    failures = sum(b['state'] in ('FAILED', 'HALTED') for b in blocks)
    state = status[0]
    if state == 'COMPLETE' and (completed != expected or failures):
        state = 'INCOMPLETE'
    phases = []
    for period in sorted({b['period'] for b in blocks}):
        group = [b for b in blocks if b['period'] == period]
        phases.append({'period': period, 'expected': 34,
            'completed': sum(b['state'] == 'SUCCESS' and not b['national'] for b in group),
            'failed': sum(b['state'] in ('FAILED', 'HALTED') for b in group),
            'national': next((b['state'] for b in group if b['national']), 'NOT_STARTED')})
    return {'state': state, 'expected': expected, 'completed': completed, 'failed': failures,
        'nationalCompleted': sum(b['state'] == 'SUCCESS' and b['national'] for b in blocks),
        'startedAt': status[1].get('startedAt'), 'phases': phases, 'blocks': blocks}


def daily_record(report_day, *, now=None):
    now = now or datetime.now(timezone.utc)
    root = DAILY_ROOT.resolve()
    path = root / str(report_day) / 'crawl_state.sqlite'
    base = {'reportDate': str(report_day), 'runDate': str(report_day + timedelta(days=1)),
        'state': 'NOT_STARTED', 'expected': 102, 'completed': 0, 'failed': 0,
        'nationalCompleted': 0, 'updatedAt': None, 'phases': [], 'blocks': []}
    try:
        if not path.exists():
            return base
        if path.is_symlink() or path.parent.is_symlink() or path.resolve().parent.parent != root:
            raise ValueError('Unsafe checkpoint')
        stat = path.stat()
        data = _checkpoint(str(path), stat.st_mtime_ns, stat.st_size)
        state = data['state']
        # A stale RUNNING checkpoint is not proof of a live process.
        if state == 'RUNNING' and now.timestamp() - stat.st_mtime > 1200:
            state = 'NEEDS_CHECK'
        return {**base, **data, 'state': state,
            'updatedAt': datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat()}
    except (OSError, sqlite3.Error, ValueError, TypeError, KeyError):
        return {**base, 'state': 'UNREADABLE'}


def source_status(db, day, runs=None):
    if not ready(db):
        return {'state': 'UNAVAILABLE', 'completed': 0, 'expected': None}
    run = runs.get(day) if runs is not None else db.get(SourceMonitorRun, day)
    if run is None:
        return {'state': 'not-started', 'completed': 0, 'expected': None}
    return {'state': run.state, 'completed': len(run.details.get('completed', [])),
        'expected': run.details.get('expected'), 'updatedAt': run.updated_at.isoformat(),
        'reason': run.details.get('reason')}


def monitoring_index(db, days):
    """Batch queries for the displayed range, not one SQL query per historical day."""
    if not days or not ready(db): return {}, {}
    runs = {r.day: r for r in db.scalars(select(SourceMonitorRun).where(SourceMonitorRun.day.in_(days)))}
    lower, upper = date_bounds(min(days), max(days))
    alerts = db.execute(select(SourceMonitorAlert.id, SourceMonitorAlert.created_at,
        SourceMonitorAlert.updated_at, SourceMonitorAlert.details).where(
        SourceMonitorAlert.updated_at >= lower, SourceMonitorAlert.created_at < upper))
    counts = {day: set() for day in days}
    for identifier, created, updated, details in alerts:
        contexts = details.get('contexts', [])
        affected = set()
        for context in contexts:
            try: affected.add(date.fromisoformat(context.get('reportDate', '')) + timedelta(days=1))
            except (ValueError, TypeError): pass
        if not affected:
            stamp = created if created.tzinfo else created.replace(tzinfo=timezone.utc)
            affected.add(stamp.astimezone(VIETNAM).date())
        for day in affected:
            if day in counts: counts[day].add(identifier)
    return runs, {day: len(values) for day, values in counts.items()}


def today_report(db, *, now=None):
    now = now or datetime.now(timezone.utc)
    day = now.astimezone(VIETNAM).date()
    daily = daily_record(day - timedelta(days=1), now=now)
    daily.pop('blocks', None)
    if daily['state'] == 'NOT_STARTED' and now.astimezone(VIETNAM).hour < 5:
        daily['state'] = 'NOT_DUE'
    source = source_status(db, day)
    if source['state'] == 'not-started' and now.astimezone(VIETNAM).hour < 6:
        source['state'] = 'not-due'
    alert_counts = None
    if ready(db):
        from .source_monitor_batches import batch_key
        alert_counts = {'open': db.scalar(select(func.count(func.distinct(batch_key()))).select_from(SourceMonitorAlert).where(SourceMonitorAlert.resolved_at.is_(None))),
            'unread': db.scalar(select(func.count(func.distinct(batch_key()))).select_from(SourceMonitorAlert).where(SourceMonitorAlert.resolved_at.is_(None), SourceMonitorAlert.read_at.is_(None)))}
    control = db.get(CollectionControl, 'dvcqg')
    from .recapture_log import recapture_page
    recaptures = recapture_page(1, day, day, now=now)['items']
    return {'day': str(day), 'daily': daily, 'source': source, 'alerts': alert_counts,
        'control': control.circuit_state if control else 'unknown',
        'checkedAt': now.isoformat(), 'recaptures': recaptures,
        'needsRefresh': daily['state'] == 'RUNNING' or source['state'] in ('running', 'waiting')
            or any(r['state'] in {'RUNNING', 'WAITING_FOR_COLLECTOR'} for r in recaptures)}


def daily_page(db, page, start, end, state, issues_only, *, now=None):
    now = now or datetime.now(timezone.utc)
    today = now.astimezone(VIETNAM).date()
    date_bounds(start, end)
    # Dates in this API are execution dates, not report dates.
    first = max(start or FIRST_VALID_REPORT_DATE + timedelta(days=1), FIRST_VALID_REPORT_DATE + timedelta(days=1))
    last = min(end or today, today)
    days = [last - timedelta(days=i) for i in range(max(0, (last - first).days + 1))]
    selected = None
    monitor_days = days if state or issues_only else days[(min(page,max(1,(len(days)+9)//10))-1)*10:min(page,max(1,(len(days)+9)//10))*10]
    runs, alerts = monitoring_index(db, monitor_days)
    if state or issues_only:
        selected = []
        for day in days:
            run = daily_record(day - timedelta(days=1), now=now)
            sample = source_status(db, day, runs)
            issue = run['state'] in ('FAILED', 'HALTED', 'INCOMPLETE', 'UNREADABLE', 'NEEDS_CHECK') or run['failed'] > 0
            issue = issue or (run['state'] == 'NOT_STARTED' and (day < today or now.astimezone(VIETNAM).hour >= 5))
            issue = issue or sample['state'] in ('incomplete', 'paused', 'UNAVAILABLE', 'not-checked') or alerts.get(day,0)>0
            issue = issue or sample['state']=='not-started' and (day<today or now.astimezone(VIETNAM).hour>=6)
            if (not state or run['state'] == state) and (not issues_only or issue):
                selected.append((day, run, sample))
        total = len(selected)
    else:
        total = len(days)
    page, offset = paging(page, total)
    records = selected[offset:offset+PAGE_SIZE] if selected is not None else [
        (day, daily_record(day-timedelta(days=1), now=now), source_status(db, day, runs)) for day in days[offset:offset+PAGE_SIZE]]
    items = []
    for day, daily, sample in records:
        daily = {k: v for k, v in daily.items() if k not in ('blocks', 'phases')}
        items.append({**daily, 'source': sample, 'alerts': alerts.get(day,0)})
    return {'items': items, 'total': total, 'page': page, 'pageSize': PAGE_SIZE}


def daily_detail(db, report_day, page, state=None):
    if report_day < FIRST_VALID_REPORT_DATE or report_day >= datetime.now(timezone.utc).astimezone(VIETNAM).date():
        raise HTTPException(404, 'Ngày dữ liệu không thuộc lịch sử khai thác.')
    record = daily_record(report_day)
    blocks = record.pop('blocks')
    if state == 'issues':
        blocks = [b for b in blocks if b['state'] in ('FAILED', 'HALTED')]
    elif state:
        blocks = [b for b in blocks if b['state'] == state]
    blocks.sort(key=lambda b: (b['period'], b.get('province') or '', b['key']))
    total = len(blocks); page, offset = paging(page, total)
    items = blocks[offset:offset+PAGE_SIZE]
    ids = []
    for block in items:
        try: ids.append(uuid.UUID(block['rootId']))
        except (ValueError, TypeError, AttributeError): pass
    names = {str(k): v for k, v in db.execute(select(Department.id, Department.name).where(Department.id.in_(ids)))} if ids else {}
    return {**record, 'items': [{**b, 'province': b['province'] or names.get(b['rootId']) or ('Toàn quốc' if b['national'] else 'Chưa xác định')} for b in items],
        'total': total, 'page': page, 'pageSize': PAGE_SIZE,
        'source': source_status(db, report_day+timedelta(days=1))}
