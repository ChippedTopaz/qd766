"""Source signatures and closed-month drafts. No publication, collection job or Credit mutation."""
import hashlib,json,math,uuid
from datetime import datetime,timezone
from decimal import Decimal
from pathlib import Path
from sqlalchemy import select,inspect
from .models import SourceMonitorBaseline,SourceMonitorSample,SourceMonitorAlert,NationalSummarySnapshot,DailyObservation
from .province_refresh import VIETNAM
from .dashboard import GROUP_LABELS

TABLES=('source_monitor_baselines','source_monitor_samples','source_monitor_alerts','source_monitor_runs')
def ready(db):
    # Cache only within this short-lived session, never across a schema upgrade.
    if 'source_monitor_ready' not in db.info:
        inspector=inspect(db.connection())
        db.info['source_monitor_ready']=all(inspector.has_table(name) for name in TABLES)
    return db.info['source_monitor_ready']
def scalar(value):
    if isinstance(value,(int,float,Decimal)) and not isinstance(value,bool):
        if not math.isfinite(float(value)):raise ValueError('Non-finite source number')
        number=Decimal(str(value))
        return '0' if number==0 else format(number.normalize(),'f')
    if value is None or isinstance(value,(str,bool)):return value
    raise ValueError('Unsupported source scalar')
def fingerprint(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()
def differences(before,after):
    return [{'field':key,'before':before.get(key),'after':after.get(key),
             'change':'added' if key not in before else 'removed' if key not in after else 'changed'}
            for key in sorted(before.keys()|after.keys()) if key not in before or key not in after or before[key]!=after[key]]
def alert(db,kind,title,key,details,*,now=None):
    now=now or datetime.now(timezone.utc);digest=fingerprint([kind,key])
    item=db.scalar(select(SourceMonitorAlert).where(SourceMonitorAlert.dedupe_key==digest).with_for_update())
    if item is None:
        item=SourceMonitorAlert(dedupe_key=digest,kind=kind,title=title,details=details,created_at=now,updated_at=now,occurrences=1)
        db.add(item)
    else:
        item.occurrences+=1;item.updated_at=now
        contexts={fingerprint(c):c for c in item.details.get('contexts',[])+details.get('contexts',[])}
        item.details={**item.details,**details,'contexts':list(contexts.values())[:102]}
        if item.resolved_at is not None:item.resolved_at=None;item.read_at=None
    return item

def structure_profile(data):
    """Declared fields only; counts/scores/row order/unit names are not a scoring structure."""
    root=data.get('overview') or data.get('parent')
    if not isinstance(root,dict) or not root.get('departmentId'):raise ValueError('Missing source root')
    rows=[root,*data.get('evaluation',data.get('children',[]))];profile={}
    buckets={}
    for index,row in enumerate(rows):
        if not isinstance(row,dict):raise ValueError('Invalid source entity')
        cohort='root' if index==0 else 'child:'+':'.join(str(row.get(k,'')) for k in ('departmentType','departmentLevel','agencyLevel','level'))
        fields={}
        for key in ('totalMaxScore','formula','formulaVersion','threshold','scorePolicy'):
            if key in row and (row[key] is None or isinstance(row[key],(str,int,float,bool))):fields[key]=scalar(row[key])
        metrics=row.get('metrics',[])
        if not isinstance(metrics,list):raise ValueError('Invalid metric list')
        for metric in metrics:
            if not isinstance(metric,dict) or not isinstance(metric.get('code'),str) or not metric['code']:raise ValueError('Missing metric identity')
            code=metric['code'];fields['metric:'+code]=True
            for key in ('name','maxScore','threshold','targetRatio','formula','formulaVersion','weight'):
                if key in metric:fields['metric:'+code+':'+key]=scalar(metric[key])
        for key,value in fields.items():buckets.setdefault(cohort+'/'+key,{})[fingerprint(value)]=value
    for key,values in buckets.items():profile[key]=sorted(values.values(),key=lambda v:json.dumps(v,ensure_ascii=False))
    return profile

def observe_profile(db,key,profile,context,*,seed=None):
    if not ready(db):return None
    old=db.get(SourceMonitorBaseline,key);now=datetime.now(timezone.utc)
    if old is None:
        old=SourceMonitorBaseline(key=key,profile=seed or profile,fingerprint=fingerprint(seed or profile),updated_at=now);db.add(old);db.flush()
    # Inventory churn is not proof of indicator removal. Compare common cohorts.
    common={k.split('/')[0] for k in old.profile}&{k.split('/')[0] for k in profile}
    before={k:v for k,v in old.profile.items() if k.split('/')[0] in common}
    after={k:v for k,v in profile.items() if k.split('/')[0] in common}
    changes=differences(before,after)
    item=None
    if changes:
        group_name=GROUP_LABELS.get(context['group'],'Cơ cấu nhóm chỉ tiêu')
        item=alert(db,'structure','Thay đổi cơ cấu điểm/chỉ tiêu: '+group_name,
            [context['periodType'],context['group'],fingerprint(before),fingerprint(after)],
            {'changes':changes[:200],'changeCount':len(changes),'contexts':[context],
             'requiresRecrawl':True,'confirmed':False,'note':'Đối chiếu cơ cấu; không tự sửa công thức hoặc xoá lịch sử.'})
        roots={c.get('rootId') for c in item.details['contexts']}
        item.details={**item.details,'confirmed':len(roots)>1}
    old.profile=profile;old.fingerprint=fingerprint(profile);old.updated_at=now
    return item

def national_profile(data):
    rows=data.get('evaluation')
    if not isinstance(rows,list) or not rows:raise ValueError('Missing national evaluation')
    if any(not isinstance(row,dict) or not isinstance(row.get('groupScores'),dict) for row in rows):
        raise ValueError('Invalid national group structure')
    codes={tuple(sorted(row['groupScores'])) for row in rows}
    return {'root/groupCodes':sorted([list(c) for c in codes])}

def capture_profiles(directory,manifest):
    directory=Path(directory).resolve();result={}
    for capture in manifest['captures']:
        path=(directory/capture['file']).resolve()
        if not path.is_relative_to(directory) or path.stat().st_size>20*1024*1024:raise ValueError('Unsafe/oversized capture')
        raw=path.read_bytes()
        if hashlib.sha256(raw).hexdigest()!=capture['sha256']:raise ValueError('Capture hash mismatch')
        envelope=json.loads(raw)
        if envelope.get('code')!='OK' or not isinstance(envelope.get('data'),dict):raise ValueError('Invalid source envelope')
        result[capture['group']]=structure_profile(envelope['data'])
    return result

def observe_daily_structure(db,root_id,period,report_date,directory,manifest,*,capture_root,root_name=None):
    if not ready(db):return
    profiles=capture_profiles(directory,manifest);seeds={}
    keys=[f'{root_id}:{period.type}:{group}' for group in profiles]
    existing=set(db.scalars(select(SourceMonitorBaseline.key).where(SourceMonitorBaseline.key.in_(keys))))
    previous=None if len(existing)==len(keys) else db.scalar(select(DailyObservation).where(DailyObservation.root_department_id==root_id,
        DailyObservation.period_type==period.type,DailyObservation.year==period.year,DailyObservation.period_value==period.value,
        DailyObservation.report_date<report_date).order_by(DailyObservation.report_date.desc()).limit(1))
    if previous:
        folder=Path(capture_root)/str(previous.report_date)/'captures'/f'{period.type}-{period.year}-{period.value or 0}'/str(root_id)
        try:seeds=capture_profiles(folder,json.loads((folder/'manifest.json').read_text(encoding='utf-8')))
        except (OSError,ValueError,KeyError):pass # Missing raw baseline starts a new profile, never invents one.
    for group,profile in profiles.items():
        observe_profile(db,f'{root_id}:{period.type}:{group}',profile,
            {'rootId':str(root_id),'rootName':root_name or str(root_id),'periodType':period.type,'year':period.year,'value':period.value,'group':group,'reportDate':str(report_date)},seed=seeds.get(group))

def score_profile(data):
    def score(value):
        if isinstance(value,bool) or not isinstance(value,(int,float,Decimal)):
            raise ValueError('Invalid source score')
        return scalar(value)
    result={}
    for row in data['evaluation']:
        identifier=str(uuid.UUID(str(row['departmentId'])))
        if identifier in result:raise ValueError('Duplicate province')
        if not isinstance(row.get('groupScores'),dict) or not row['groupScores']:
            raise ValueError('Missing source group scores')
        result[identifier]={'total':score(row['totalScore']),**{key:score(value) for key,value in sorted(row['groupScores'].items())}}
    return result

def closed_month_baselines(db,now):
    local=now.astimezone(VIETNAM);rows=db.scalars(select(NationalSummarySnapshot).where(
        NationalSummarySnapshot.period_type=='month',NationalSummarySnapshot.completeness_state=='complete',
        NationalSummarySnapshot.group_count==6).order_by(NationalSummarySnapshot.captured_at.desc()))
    result={}
    for row in rows:
        if row.year<2026 or (row.year,row.period_value)>=(local.year,local.month):continue
        result.setdefault((row.year,row.period_value),row)
    return sorted(result.values(),key=lambda r:(r.year,r.period_value),reverse=True)

def record_month_sample(db,baseline,capture,*,now=None):
    if (capture.period.type,capture.period.year,capture.period.value)!=('month',baseline.year,baseline.period_value):raise ValueError('Sample period mismatch')
    now=now or datetime.now(timezone.utc);before,after=score_profile(baseline.response_data),score_profile(capture.response_data)
    if set(before)!=set(after):raise ValueError('Province inventories differ; no score comparison')
    flat=lambda p:{f'{identity}/{group}':score for identity,groups in p.items() for group,score in groups.items()}
    changes=differences(flat(before),flat(after));key=f'month-{baseline.year}-{baseline.period_value:02d}'
    item=db.get(SourceMonitorSample,key);digest=fingerprint(after)
    stamp=lambda value:value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    verified=bool(item and item.fingerprint==digest and item.baseline_id==baseline.id and stamp(item.checked_at).astimezone(VIETNAM).date()!=stamp(now).astimezone(VIETNAM).date())
    if item is None:item=SourceMonitorSample(key=key,year=baseline.year,month=baseline.period_value);db.add(item)
    item.baseline_id=baseline.id;item.fingerprint=digest;item.payload=after;item.checked_at=now
    if changes:
        alert(db,'closed-period',f'Điểm tháng {baseline.period_value}/{baseline.year} khác dữ liệu đang lưu',
            [key,str(baseline.id),digest],{'period':key,'baselineId':str(baseline.id),'changes':changes[:240],
                'changeCount':len(changes),'confirmed':verified,'sampleOnly':True,'requiresRecrawl':True,
                'provinceNames':{str(row['departmentId']):row.get('departmentName','') for row in baseline.response_data['evaluation']},
                'note':'Mẫu điểm tỉnh, không bảo đảm phát hiện mọi thay đổi chi tiết cơ quan.'},now=now)
    return len(changes)
