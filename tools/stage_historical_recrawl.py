"""Operator-requested raw recapture. NEVER imports or publishes snapshots.

Only production writes allowed: the existing shared collector lease. Source
captures, comparisons, checkpoint and report are confined to an ignored folder.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import socket
import sys
import time
from datetime import date, datetime, timezone, timedelta
from sqlalchemy import select, text, event

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from qd766.backend.config import Settings, load_environment_file
from qd766.backend.database import create_database_engine, create_session_factory
from qd766.backend.models import CollectionControl, CollectionJob, Snapshot, Dataset, Entity, NationalSummarySnapshot
from qd766.backend.jobs import acquire_collection_lease, release_collection_lease
from qd766.collection import SafetyStop, plan_evaluation_requests
from qd766.concurrent_collection import PooledHttpTransport, collect_concurrent_snapshot
from qd766.national_summary import collect_national_summary
from qd766.periods import PeriodSelection
from qd766.province_roots import load_province_roots
from qd766.snapshot import build_collected_snapshot


def write_json(path, payload):
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding='utf-8')
    temporary.replace(path)


def periods_for(today):
    return ([PeriodSelection('month', today.year, m) for m in range(1, today.month + 1)]
            + [PeriodSelection('quarter', today.year, q) for q in range(1, (today.month - 1) // 3 + 2)]
            + [PeriodSelection('year', today.year)])


def sql_guard(conn, cursor, statement, parameters, context, executemany):
    sql = ' '.join(statement.lower().split())
    if sql.startswith(('select ', 'set ', 'show ')):
        return
    if sql.startswith('update collection_controls set ') or sql.startswith('update public.collection_controls set '):
        return
    raise RuntimeError('STAGING_NO_PUBLICATION_SQL_GUARD')


def projection(entities):
    return {str(e.department_id): {'score': float(e.api_score) if e.api_score is not None else None,
                                 'maximum': float(e.api_max_score) if e.api_max_score is not None else None}
            for e in entities}


def score_diff(before, after):
    changes = []
    for group in sorted(before.keys() | after.keys()):
        old, new = before.get(group, {}), after.get(group, {})
        for identity in sorted(old.keys() | new.keys()):
            a, b = old.get(identity), new.get(identity)
            if a != b:
                changes.append({'group': group, 'departmentId': identity, 'before': a, 'after': b})
    return changes


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--run-day', type=date.fromisoformat, required=True)
    parser.add_argument('--backup', type=Path)
    parser.add_argument('--stop-after', type=int, default=0, help='Optional bounded first-run validation')
    args = parser.parse_args()
    today = datetime.now(timezone(timedelta(hours=7))).date()
    if args.run_day > today or args.run_day.year != today.year:
        raise ValueError('Run day must be within the current year and not in the future')
    periods = periods_for(args.run_day)
    roots = sorted(load_province_roots().values(), key=lambda r: r.province_code)
    if len(roots) != 34:
        raise ValueError('Expected 34 verified provinces')
    folder = ROOT / '.tmp-historical-recapture' / args.run_day.strftime('%Y%m%d')
    plan = {'runDay': str(args.run_day), 'scope': 'all', 'periods': [[p.type, p.year, p.value] for p in periods],
            'provinceBlocks': len(periods) * 34, 'nationalBlocks': len(periods),
            'minimumRequests': len(periods) * 205, 'publicationAllowed': False,
            'maxHttpRequestsInFlight': 2, 'output': str(folder)}
    if not args.execute:
        print(json.dumps(plan), flush=True)
        return 0
    backup = args.backup.resolve() if args.backup else None
    if not backup or not backup.is_relative_to(folder.resolve() / 'archive') or not backup.is_file():
        raise ValueError('An archived database backup for this run is required')
    if backup.read_bytes()[:5] != b'PGDMP':
        raise ValueError('Invalid database archive')
    with backup.open('rb') as stream:
        backup_hash = hashlib.file_digest(stream, 'sha256').hexdigest()
    if backup_hash != Path(str(backup) + '.sha256').read_text().split()[0].lower():
        raise ValueError('Database archive checksum mismatch')
    folder.mkdir(parents=True, exist_ok=True)
    checkpoint_path = folder / 'checkpoint.json'
    report = json.loads(checkpoint_path.read_text(encoding='utf-8')) if checkpoint_path.exists() else {
        **plan, 'backup': str(backup), 'backupSha256': backup_hash, 'startedAt': str(datetime.now(timezone.utc)), 'blocks': {}}
    if report['periods'] != plan['periods'] or report['backupSha256'] != backup_hash:
        raise ValueError('Resume plan/archive mismatch')
    load_environment_file(ROOT / '.env')
    engine = create_database_engine(Settings.from_env())
    event.listen(engine, 'before_cursor_execute', sql_guard)
    factory = create_session_factory(engine)
    # A dedicated connection holds a session-level lock for the entire run,
    # including time spent yielding the per-block collection lease to users.
    run_lock = engine.connect()
    if not run_lock.scalar(text('SELECT pg_try_advisory_lock(7661016)')):
        run_lock.close()
        raise RuntimeError('A staged recapture is already running')
    run_lock.commit()
    owner = f'staged-recapture:{socket.gethostname()}:{os.getpid()}'
    active = False

    def save(state):
        report['state'] = state
        report['updatedAt'] = str(datetime.now(timezone.utc))
        report['completed'] = sum(b['state'] == 'SUCCESS' for b in report['blocks'].values())
        report['failed'] = sum(b['state'] == 'FAILED' for b in report['blocks'].values())
        report['scoreChanges'] = sum(b.get('scoreChanges', 0) for b in report['blocks'].values())
        write_json(checkpoint_path, report)

    def release():
        nonlocal active
        if active:
            with factory.begin() as db:
                c = db.get(CollectionControl, 'dvcqg')
                if c and c.lease_locked_by == owner:
                    release_collection_lease(db, owner)
            active = False

    def acquire():
        nonlocal active
        deadline = time.monotonic() + 3600
        while True:
            # Yield to queued user requests rather than reserve the full run.
            with factory.begin() as db:
                busy = db.scalar(select(CollectionJob.id).where(CollectionJob.state.in_(['queued', 'running'])).limit(1))
                state = 'busy' if busy else acquire_collection_lease(db, owner, lease_seconds=900)
            if state == 'acquired':
                active = True
                return
            if state == 'circuit-open':
                raise SafetyStop('Existing safety pause; no bypass')
            if time.monotonic() >= deadline:
                raise SafetyStop('Shared collector remained busy; resume this run later')
            save('WAITING_FOR_COLLECTOR')
            time.sleep(10)

    def guard():
        with factory.begin() as db:
            c = db.scalar(select(CollectionControl).where(CollectionControl.key == 'dvcqg').with_for_update())
            if not c or c.circuit_state != 'closed' or c.lease_locked_by != owner:
                raise SafetyStop('Collector lease or safety state changed')
            c.lease_locked_at = datetime.now(timezone.utc)

    def baseline(period, root_id, target):
        if target.exists():
            return json.loads(target.read_text(encoding='utf-8'))
        with factory() as db:
            db.execute(text('SET TRANSACTION READ ONLY'))
            db.execute(text("SET LOCAL statement_timeout='20s'"))
            if root_id is None:
                row = db.scalar(select(NationalSummarySnapshot).where(NationalSummarySnapshot.period_type == period.type,
                    NationalSummarySnapshot.year == period.year, NationalSummarySnapshot.period_value == period.value)
                    .order_by(NationalSummarySnapshot.captured_at.desc()).limit(1))
                result = {'id': str(row.id) if row else None, 'data': row.response_data if row else None}
            else:
                row = db.scalar(select(Snapshot).where(Snapshot.root_department_id == root_id, Snapshot.scope == 'all',
                    Snapshot.state == 'complete', Snapshot.period_type == period.type, Snapshot.year == period.year,
                    Snapshot.period_value == period.value).order_by(Snapshot.created_at.desc()).limit(1))
                values = {}
                if row:
                    for dataset in db.scalars(select(Dataset).where(Dataset.snapshot_id == row.id)):
                        values[dataset.group_name] = projection(db.scalars(select(Entity).where(Entity.dataset_id == dataset.id)))
                result = {'id': str(row.id) if row else None, 'scores': values}
        write_json(target, result)
        return result

    transport = PooledHttpTransport(max_workers=2, spacing=.6, guard=guard)
    new_blocks = 0
    try:
        save('RUNNING')
        for period in periods:
            label = f'{period.type}-{period.year}-{period.value or 0}'
            for root in [None, *roots]:
                identity = str(root.root_department_id) if root else 'national'
                key = label + ':' + identity
                output = folder / 'captures' / label / identity
                output.mkdir(parents=True, exist_ok=True)
                old_state = report['blocks'].get(key, {})
                if old_state.get('state') == 'SUCCESS':
                    if not (output / 'validated.json').exists() or hashlib.sha256(
                            (output / 'validated.json').read_bytes()).hexdigest() != old_state.get('validatedSha256'):
                        raise ValueError('Validated block missing; refusing resume')
                    continue
                report['blocks'][key] = {'state': 'RUNNING', 'name': root.province_name if root else 'Cả nước'}
                save('RUNNING')
                old = baseline(period, root.root_department_id if root else None, output / 'baseline.json')
                try:
                    acquire()
                    for attempt in range(3):
                        try:
                            if root is None:
                                class RecordedNational:
                                    def post_json(self, url, request):
                                        response = transport.post_json(url, request)
                                        raw = output / 'national-response.json'
                                        temporary = raw.with_suffix('.tmp')
                                        temporary.write_bytes(response.body)
                                        temporary.replace(raw)
                                        return response
                                capture = collect_national_summary(period, RecordedNational())
                                payload = {'period': [period.type, period.year, period.value],
                                    'capturedAt': str(capture.captured_at), 'rawSha256': capture.raw_sha256,
                                    'request': capture.request_payload, 'data': capture.response_data}
                                write_json(output / 'national.json', payload)
                                from qd766.backend.source_monitor import score_profile
                                before = score_profile(old['data']) if old['data'] else {}
                                after = score_profile(capture.response_data)
                                changes = [{'departmentId': k, 'before': before.get(k), 'after': after.get(k)}
                                    for k in sorted(before.keys() | after.keys()) if before.get(k) != after.get(k)]
                            else:
                                collect_concurrent_snapshot(plan_evaluation_requests(period, identity), period=period,
                                    output_dir=output, transport=transport, max_workers=2, max_retries=3)
                                payload = build_collected_snapshot(output).to_dict()
                                after = {d['group']: {e['departmentId']: {'score': e['apiScore'], 'maximum': e['apiMaxScore']}
                                    for e in [d['root'], *d['children']]} for d in payload['datasets']}
                                changes = score_diff(old['scores'], after)
                            write_json(output / 'validated.json', payload)
                            write_json(output / 'score-changes.json', changes)
                            break
                        except SafetyStop:
                            raise
                        except Exception:
                            if attempt == 2:
                                raise
                            time.sleep(2 ** (attempt + 1))
                    report['blocks'][key].update(state='SUCCESS', scoreChanges=len(changes), baselineId=old['id'],
                        validatedSha256=hashlib.sha256((output / 'validated.json').read_bytes()).hexdigest())
                    print(json.dumps({'block': key, **report['blocks'][key]}, ensure_ascii=False), flush=True)
                except SafetyStop:
                    report['blocks'][key]['state'] = 'HALTED'
                    raise
                except Exception as error:
                    report['blocks'][key].update(state='FAILED', error=type(error).__name__)
                    print(json.dumps({'block': key, **report['blocks'][key]}, ensure_ascii=False), flush=True)
                finally:
                    release()
                save('RUNNING')
                new_blocks += 1
                if args.stop_after and new_blocks >= args.stop_after:
                    save('BOUNDED_CHECK_COMPLETE')
                    return 0
                time.sleep(3)
        save('AWAITING_ADMIN_REVIEW' if report['completed'] == len(periods) * 35 else 'INCOMPLETE')
        print(json.dumps({k: v for k, v in report.items() if k != 'blocks'}, ensure_ascii=False), flush=True)
        return 0 if report['state'] == 'AWAITING_ADMIN_REVIEW' else 1
    except SafetyStop as error:
        report['stopReason'] = str(error)
        save('HALTED')
        return 2
    except BaseException:
        save('INTERRUPTED')
        raise
    finally:
        release()
        transport.close()
        run_lock.execute(text('SELECT pg_advisory_unlock(7661016)'))
        run_lock.commit()
        run_lock.close()
        engine.dispose()


if __name__ == '__main__':
    raise SystemExit(main())
