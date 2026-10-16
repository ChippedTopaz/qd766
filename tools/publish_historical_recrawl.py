"""Publish an explicitly approved staged recapture, atomically; archive old day links.

No source calls, schema changes, formula changes, account or wallet writes.
Old snapshots and national summaries are retained. Replaced daily links are
exported and checksummed before the exact exported IDs leave the active table.
"""
import argparse
import gc
import hashlib
import json
import os
from pathlib import Path
import socket
import sys
import uuid
from datetime import date, datetime, timezone
from sqlalchemy import select, delete, text, event

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from qd766.backend.config import Settings,load_environment_file
from qd766.backend.database import create_database_engine,create_session_factory
from qd766.backend.models import Snapshot,Dataset,Department,DailyObservation,NationalSummarySnapshot,CollectionControl,CollectionJob
from qd766.backend.importer import store_normalized_snapshot
from qd766.backend.national_summaries import store_national_summary
from qd766.backend.daily_history import daily_target,validate_daily_snapshot
from qd766.backend.jobs import acquire_collection_lease,release_collection_lease
from qd766.national_summary import NationalSummaryCapture
from qd766.periods import PeriodSelection
from qd766.province_roots import load_province_roots


def digest(path):
    with path.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def save(path,value):
    temporary=path.with_suffix(path.suffix+'.tmp')
    temporary.write_text(json.dumps(value,ensure_ascii=False,indent=2,default=str),encoding='utf-8')
    temporary.replace(path)


def publication_sql_guard(conn,cursor,statement,parameters,context,executemany):
    sql=' '.join(statement.lower().split())
    if sql.startswith(('select ','set ','show ','savepoint ','release savepoint ','rollback to savepoint ')):return
    allowed_inserts={'snapshots','datasets','entities','metrics','departments','national_summary_snapshots','daily_observations'}
    allowed_updates={'departments','snapshots','collection_controls'}
    if any(sql.startswith('insert into '+table+' ') for table in allowed_inserts):return
    if any(sql.startswith('update '+table+' set ') for table in allowed_updates):return
    if sql.startswith('delete from daily_observations where daily_observations.id in ('):return
    raise RuntimeError('PUBLICATION_SQL_OUTSIDE_APPROVED_SCOPE')


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--execute',action='store_true')
    parser.add_argument('--run-day',type=date.fromisoformat,required=True)
    parser.add_argument('--backup',type=Path,required=True)
    args=parser.parse_args()
    directory=ROOT/'.tmp-historical-recapture'/args.run_day.strftime('%Y%m%d')
    cp=json.loads((directory/'checkpoint.json').read_text(encoding='utf-8'))
    now=datetime.now(timezone.utc)
    report_day,boundary,open_periods=daily_target(now)
    if args.run_day.isoformat()!='2026-10-16' or report_day!=date(2026,10,15):
        raise ValueError('Approved run/report-day guard failed; re-review before publishing')
    if cp['state']!='AWAITING_ADMIN_REVIEW' or cp['completed']!=525 or cp['failed']!=0 or len(cp['blocks'])!=525:
        raise ValueError('Run is not complete/awaiting approval')
    archive=directory/'archive'
    backup=args.backup.resolve()
    if not backup.is_relative_to((archive/'pre-publish').resolve()):raise ValueError('Wrong backup folder')
    with backup.open('rb') as stream:
        if stream.read(5)!=b'PGDMP':raise ValueError('Wrong backup format')
    backup_hash=digest(backup)
    if backup_hash!=Path(str(backup)+'.sha256').read_text().split()[0].lower():raise ValueError('Backup checksum failed')
    if now.timestamp()-backup.stat().st_mtime>7200:raise ValueError('Pre-publication backup is too old')
    roots={str(r.root_department_id) for r in load_province_roots().values()}
    periods={f'{p[0]}-{p[1]}-{p[2] or 0}':PeriodSelection(p[0],p[1],p[2]) for p in cp['periods']}
    if len(roots)!=34 or len(periods)!=15 or set(cp['blocks'])!={p+':'+r for p in periods for r in roots|{'national'}}:
        raise ValueError('Scope inventory mismatch')
    # Check every raw and normalized hash before opening a writing transaction.
    for key,block in cp['blocks'].items():
        label,identity=key.split(':',1);folder=directory/'captures'/label/identity
        if block['state']!='SUCCESS' or digest(folder/'validated.json')!=block['validatedSha256']:raise ValueError('Staged hash failed')
        if identity=='national':
            capture=json.loads((folder/'validated.json').read_text(encoding='utf-8'))
            if digest(folder/'national-response.json')!=capture['rawSha256']:raise ValueError('National hash failed')
        else:
            manifest=json.loads((folder/'manifest.json').read_text(encoding='utf-8'))
            if manifest['status']!='complete' or len(manifest['captures'])!=6:raise ValueError('Incomplete manifest')
            for cap in manifest['captures']:
                path=(folder/cap['file']).resolve()
                if not path.is_relative_to(folder.resolve()) or digest(path)!=cap['sha256']:raise ValueError('Raw capture hash failed')
    if not args.execute:
        print(json.dumps({'preflight':'PASS','snapshots':510,'nationalSummaries':15,'newDailyLinks':102,'reportDate':str(report_day),'backupSha256':backup_hash}));return 0
    from qd766.backend.collection_maintenance import user_collection_paused
    if not user_collection_paused():raise ValueError('New user collections must remain paused')
    load_environment_file(ROOT/'.env');engine=create_database_engine(Settings.from_env())
    event.listen(engine,'before_cursor_execute',publication_sql_guard)
    factory=create_session_factory(engine)
    lock=engine.connect()
    if not lock.scalar(text('SELECT pg_try_advisory_lock(7661017)')):raise RuntimeError('Publication already running')
    lock.commit()
    owner=f'publish-recapture:{socket.gethostname()}:{os.getpid()}'
    acquired=False
    audit_path=directory/'publication-audit.json'
    audit={'state':'PREPARING','runDay':str(args.run_day),'reportDate':str(report_day),'backup':str(backup),
           'backupSha256':backup_hash,'startedAt':str(now),'snapshots':{},'summaries':{}}
    save(audit_path,audit)
    try:
        with factory.begin() as db:
            if db.scalar(select(CollectionJob.id).where(CollectionJob.state.in_(['queued','running'])).limit(1)):
                raise RuntimeError('Collection jobs are active')
            if acquire_collection_lease(db,owner,lease_seconds=900)!='acquired':raise RuntimeError('Collector unavailable')
        acquired=True
        def heartbeat():
            with factory.begin() as db:
                c=db.scalar(select(CollectionControl).where(CollectionControl.key=='dvcqg').with_for_update())
                if c.circuit_state!='closed' or c.lease_locked_by!=owner:raise RuntimeError('Collector control changed')
                c.lease_locked_at=datetime.now(timezone.utc)
        with factory.begin() as db:
            db.execute(text("SET LOCAL lock_timeout='10s'"))
            db.execute(text("SET LOCAL statement_timeout='120s'"))
            # Hold department identities strongly to avoid repeated lookup SQL
            # across 510 imports. Snapshot/entity graphs can be collected normally.
            departments=list(db.scalars(select(Department)))
            old_daily=list(db.scalars(select(DailyObservation).where(DailyObservation.report_date>=date(2026,10,6),
                DailyObservation.report_date<=report_day).order_by(DailyObservation.report_date,DailyObservation.block_key)))
            if len(old_daily)!=1020:raise ValueError('Old daily scope changed; inspect before replacement')
            exported=[{column.name:getattr(row,column.name) for column in DailyObservation.__table__.columns} for row in old_daily]
            archive_path=archive/'daily-observations-20261006-through-20261015.json'
            if archive_path.exists():
                if json.loads(archive_path.read_text(encoding='utf-8'))!=json.loads(json.dumps(exported,default=str)):
                    raise ValueError('Existing daily archive differs; no overwrite')
            else:save(archive_path,exported)
            audit['dailyArchive']={'path':str(archive_path),'rows':len(exported),'sha256':digest(archive_path)}
            save(audit_path,audit)
            for label,period in periods.items():
                folder=directory/'captures'/label/'national'
                captured=json.loads((folder/'validated.json').read_text(encoding='utf-8'))
                baseline=json.loads((folder/'baseline.json').read_text(encoding='utf-8'))
                latest=db.scalar(select(NationalSummarySnapshot.id).where(NationalSummarySnapshot.period_type==period.type,
                    NationalSummarySnapshot.year==period.year,NationalSummarySnapshot.period_value==period.value)
                    .order_by(NationalSummarySnapshot.captured_at.desc()).limit(1))
                if str(latest)!=baseline['id']:raise ValueError('Published national baseline changed')
                capture=NationalSummaryCapture(period,captured['request'],captured['data'],captured['rawSha256'],datetime.fromisoformat(captured['capturedAt']))
                summary,created=store_national_summary(db,capture,observation_id='approved-recapture-20261016:'+label)
                if not created:raise ValueError('Unexpected prior publication')
                audit['summaries'][label]=str(summary.id)
            for index,(key,block) in enumerate(cp['blocks'].items()):
                label,identity=key.split(':',1)
                if identity=='national':continue
                period=periods[label];folder=directory/'captures'/label/identity
                latest=db.scalar(select(Snapshot.id).where(Snapshot.root_department_id==uuid.UUID(identity),Snapshot.scope=='all',
                    Snapshot.state=='complete',Snapshot.period_type==period.type,Snapshot.year==period.year,Snapshot.period_value==period.value)
                    .order_by(Snapshot.created_at.desc()).limit(1))
                if str(latest)!=block['baselineId']:raise ValueError('Published detail baseline changed: '+key)
                payload=json.loads((folder/'validated.json').read_text(encoding='utf-8'))
                manifest=json.loads((folder/'manifest.json').read_text(encoding='utf-8'))
                for item in payload['datasets']:
                    item['raw']['path']=str((folder/Path(item['raw']['path']).name).relative_to(ROOT))
                snapshot=store_normalized_snapshot(db,payload,observation_id='approved-recapture-20261016:'+key)
                # Preserve actual collection time, not import/publication time.
                snapshot.created_at=max(datetime.fromisoformat(cap['capturedAt']) for cap in manifest['captures'])
                audit['snapshots'][key]=str(snapshot.id)
                if index%10==0:
                    heartbeat();save(audit_path,audit);gc.collect()
                print(json.dumps({'imported':len(audit['snapshots']),'expected':510,'period':label,'province':identity,'state':'UNCOMMITTED'}),flush=True)
            if len(audit['snapshots'])!=510 or len(audit['summaries'])!=15:raise ValueError('Incomplete import')
            heartbeat()
            # Only remove the archived, exact linkage IDs. Their source snapshots
            # and summaries stay intact in the database and the full backup.
            db.execute(delete(DailyObservation).where(DailyObservation.id.in_([r.id for r in old_daily])))
            db.flush()
            for period in open_periods:
                label=f'{period.type}-{period.year}-{period.value or 0}'
                summary=db.get(NationalSummarySnapshot,uuid.UUID(audit['summaries'][label]))
                for identity in roots:
                    snapshot=db.get(Snapshot,uuid.UUID(audit['snapshots'][label+':'+identity]))
                    validate_daily_snapshot(snapshot,summary,report_day,boundary,period,uuid.UUID(identity))
                    db.add(DailyObservation(block_key=f'daily:{report_day}:{label}:{identity}',report_date=report_day,
                        root_department_id=uuid.UUID(identity),period_type=period.type,year=period.year,period_value=period.value,
                        snapshot_id=snapshot.id,national_summary_id=summary.id,captured_at=snapshot.created_at))
            db.flush()
            count=len(list(db.scalars(select(DailyObservation.id).where(DailyObservation.report_date>=date(2026,10,6)))))
            if count!=102:raise ValueError('Daily reset must contain exactly 102 active links')
            audit['state']='READY_TO_COMMIT';audit['newDailyLinks']=102;save(audit_path,audit)
        audit['state']='PUBLISHED';audit['publishedAt']=str(datetime.now(timezone.utc));save(audit_path,audit)
        cp.update(state='PUBLISHED',publicationState='published',publishedAt=audit['publishedAt'],reportDate=str(report_day))
        save(directory/'checkpoint.json',cp)
        print(json.dumps({'publication':'PASS','snapshots':510,'summaries':15,'archivedDailyLinks':1020,'newDailyLinks':102,'reportDate':str(report_day)}),flush=True)
        return 0
    except BaseException as error:
        audit['state']='FAILED_OR_REQUIRES_VERIFICATION';audit['errorType']=type(error).__name__;save(audit_path,audit)
        raise
    finally:
        if acquired:
            with factory.begin() as db:
                control=db.get(CollectionControl,'dvcqg')
                if control.lease_locked_by==owner:release_collection_lease(db,owner)
        lock.execute(text('SELECT pg_advisory_unlock(7661017)'));lock.commit();lock.close();engine.dispose()


if __name__=='__main__':raise SystemExit(main())
