"""Admin read-only views of staged operator recaptures; never publish/retry."""
import json
from datetime import date, datetime, timezone
from functools import lru_cache
from pathlib import Path
from fastapi import HTTPException
from .admin_log_history import date_bounds, paging

RECAPTURE_ROOT = Path(__file__).resolve().parents[3] / '.tmp-historical-recapture'
STATES = {'RUNNING', 'WAITING_FOR_COLLECTOR', 'AWAITING_ADMIN_REVIEW', 'PUBLISHED', 'HALTED', 'INTERRUPTED', 'INCOMPLETE', 'BOUNDED_CHECK_COMPLETE'}


@lru_cache(maxsize=64)
def read_checkpoint(path, modified, size):
    if size > 2 * 1024 * 1024:
        raise ValueError('Oversized recapture log')
    raw = json.loads(Path(path).read_text(encoding='utf-8'))
    if not isinstance(raw, dict):
        raise ValueError('Invalid checkpoint')
    if not isinstance(raw.get('blocks'), dict) or len(raw['blocks']) > 2000:
        raise ValueError('Invalid blocks')
    periods = raw.get('periods', [])
    if not isinstance(periods, list) or len(periods) > 20:
        raise ValueError('Invalid periods')
    expected = int(raw['provinceBlocks']) + int(raw['nationalBlocks'])
    if not 1 <= expected <= 2000:
        raise ValueError('Invalid scope')
    blocks = []
    for key, block in raw['blocks'].items():
        if not isinstance(block, dict):
            raise ValueError('Invalid block')
        period, identity = key.split(':', 1)
        blocks.append({'key': key[:160], 'period': period[:40], 'province': str(block.get('name', ''))[:180],
            'state': block['state'] if block.get('state') in {'RUNNING', 'SUCCESS', 'FAILED', 'HALTED'} else 'UNREADABLE',
            'error': str(block.get('error', ''))[:80], 'national': identity == 'national',
            'scoreChanges': max(0, int(block.get('scoreChanges', 0)))})
    completed = sum(b['state'] == 'SUCCESS' for b in blocks)
    failed = sum(b['state'] in {'FAILED', 'HALTED'} for b in blocks)
    state = raw.get('state') if raw.get('state') in STATES else 'UNREADABLE'
    if state in {'AWAITING_ADMIN_REVIEW','PUBLISHED'} and (completed != expected or failed):
        state = 'INCOMPLETE'
    phases = []
    for period in sorted({b['period'] for b in blocks}):
        group = [b for b in blocks if b['period'] == period]
        phases.append({'period': period, 'expected': 34,
            'completed': sum(b['state'] == 'SUCCESS' and not b['national'] for b in group),
            'failed': sum(b['state'] in {'FAILED', 'HALTED'} for b in group),
            'national': next((b['state'] for b in group if b['national']), 'NOT_STARTED')})
    return {'state': state, 'expected': expected, 'completed': completed, 'failed': failed,
        'scope': 'all', 'provinceCount': 34, 'periods': periods, 'phases': phases,
        'nationalCompleted': sum(b['national'] and b['state'] == 'SUCCESS' for b in blocks),
        'scoreChanges': sum(b['scoreChanges'] for b in blocks),
        'startedAt': str(raw.get('startedAt', ''))[:80],
        'updatedAt': datetime.fromtimestamp(modified / 1e9, timezone.utc).isoformat(),
        'publicationState': 'published' if state=='PUBLISHED' and raw.get('publicationState')=='published' else 'not-published', 'blocks': blocks}


def recapture_record(day, *, now=None):
    root = RECAPTURE_ROOT.resolve()
    folder = root / day.strftime('%Y%m%d')
    path = folder / 'checkpoint.json'
    base = {'id': day.strftime('%Y%m%d'), 'runDate': str(day), 'state': 'UNREADABLE', 'completed': 0,
        'expected': 0, 'failed': 0, 'scope': 'all', 'provinceCount': 34, 'periods': [], 'phases': [],
        'nationalCompleted': 0, 'scoreChanges': 0, 'startedAt': None, 'updatedAt': None,
        'publicationState': 'not-published', 'blocks': []}
    try:
        if path.is_symlink() or folder.is_symlink() or path.resolve().parent.parent != root:
            raise ValueError('Unsafe checkpoint')
        stat = path.stat()
        data = read_checkpoint(str(path), stat.st_mtime_ns, stat.st_size)
        if data['state'] in {'RUNNING', 'WAITING_FOR_COLLECTOR'} and (now or datetime.now(timezone.utc)).timestamp() - stat.st_mtime > 1200:
            data = {**data, 'state': 'NEEDS_CHECK'}
        return {**base, **data}
    except (OSError, ValueError, TypeError, KeyError, OverflowError):
        return base


def recapture_page(page, start=None, end=None, state=None, *, now=None):
    date_bounds(start, end)
    root = RECAPTURE_ROOT.resolve()
    days = []
    if root.exists():
        for folder in root.iterdir():
            if len(folder.name) != 8 or not folder.name.isdigit() or folder.is_symlink() or not folder.is_dir():
                continue
            try:
                day = datetime.strptime(folder.name, '%Y%m%d').date()
            except ValueError:
                continue
            if (start is None or day >= start) and (end is None or day <= end):
                if (folder / 'checkpoint.json').exists():
                    days.append(day)
            if len(days) > 366:
                raise HTTPException(422, 'Hãy thu hẹp khoảng ngày để xem nhật ký cào lại.')
    records = [recapture_record(day, now=now) for day in sorted(days, reverse=True)]
    records = [r for r in records if not state or r['state'] == state]
    page, offset = paging(page, len(records))
    return {'items': [{k: v for k, v in r.items() if k not in {'blocks', 'phases'}} for r in records[offset:offset + 10]],
        'total': len(records), 'page': page, 'pageSize': 10}


def recapture_detail(day, page, state=None):
    record = recapture_record(day)
    blocks = record.pop('blocks')
    if state == 'issues':
        blocks = [b for b in blocks if b['state'] in {'FAILED', 'HALTED'}]
    elif state:
        blocks = [b for b in blocks if b['state'] == state]
    blocks.sort(key=lambda b: (b['period'], b['province'], b['key']))
    page, offset = paging(page, len(blocks))
    return {**record, 'items': blocks[offset:offset + 10], 'total': len(blocks), 'page': page, 'pageSize': 10}
