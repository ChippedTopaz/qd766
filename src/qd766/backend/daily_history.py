"""04:00 Vietnam reporting policy and score-only daily history."""
from datetime import date, datetime, timedelta, timezone
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from .models import DailyObservation, Snapshot, Dataset, Entity
from .dashboard import NATIONAL_GROUP_CODES, NATIONAL_GROUP_MAXIMUMS
from .province_refresh import VIETNAM, current_detail_periods

FIRST_VALID_REPORT_DATE = date(2026, 10, 6)

def daily_target(now):
    local = now.replace(tzinfo=VIETNAM) if now.tzinfo is None else now.astimezone(VIETNAM)
    boundary = local.replace(hour=4,minute=0,second=0,microsecond=0)
    if local < boundary:
        boundary -= timedelta(days=1)
    report_date = boundary.date()-timedelta(days=1)
    # At month/year rollover, finish the previous day's reporting periods first.
    periods = current_detail_periods(datetime.combine(report_date,datetime.min.time(),tzinfo=VIETNAM))
    return report_date, boundary, periods

def validate_daily_snapshot(snapshot, summary, report_date, boundary, period, root_id):
    stamp=lambda value:value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if snapshot.state!='complete' or snapshot.scope!='all' or snapshot.root_department_id!=root_id:
        raise ValueError('Invalid daily detail snapshot')
    key=(period.type,period.year,period.value)
    if (snapshot.period_type,snapshot.year,snapshot.period_value)!=key or (summary.period_type,summary.year,summary.period_value)!=key:
        raise ValueError('Mismatched daily period')
    if stamp(snapshot.created_at)<boundary or stamp(summary.captured_at)<boundary:
        raise ValueError('Cannot relabel old captures as a new reporting day')
    if summary.group_count!=6 or summary.province_count!=34 or summary.completeness_state!='complete':
        raise ValueError('National summary incomplete')
    groups={dataset.group_name for dataset in snapshot.datasets}
    if groups!=set(NATIONAL_GROUP_CODES):raise ValueError('Daily detail requires six groups')
    child_sets=[]
    for dataset in snapshot.datasets:
        roots=[item for item in dataset.entities if item.entity_kind=='root']
        if len(roots)!=1 or roots[0].api_score is None:raise ValueError('Missing root score')
        children={item.department_id for item in dataset.entities if item.entity_kind=='child'}
        child_sets.append(children)
    if any(ids!=child_sets[0] for ids in child_sets):raise ValueError('Agency list differs across groups')

def history_payload(db,root_id,unit_id,period,limit=31,include_peers=False):
    query=select(DailyObservation).where(DailyObservation.root_department_id==root_id,
        DailyObservation.period_type==period.type,DailyObservation.year==period.year,
        DailyObservation.period_value==period.value,
        DailyObservation.report_date>=FIRST_VALID_REPORT_DATE).order_by(DailyObservation.report_date.desc()).limit(limit)
    query=query.options(selectinload(DailyObservation.national_summary),selectinload(DailyObservation.snapshot)
        .selectinload(Snapshot.datasets).selectinload(Dataset.entities).selectinload(Entity.department))
    days=[]
    for record in db.scalars(query.execution_options(yield_per=5)):
        groups={}; cohort={}; total=None; rank=None; peers=[]; peer_scores={}
        if unit_id==root_id:
            evaluations=record.national_summary.response_data.get('evaluation',[])
            row=next((row for row in evaluations if row['departmentId']==str(root_id)),None)
            if row:
                total=float(row['totalScore']);peers=[float(row['totalScore']) for row in evaluations]
                groups={g:{'score':float(row['groupScores'][code]),'maximum':NATIONAL_GROUP_MAXIMUMS[g]} for g,code in NATIONAL_GROUP_CODES.items()}
                cohort={row['departmentId']:True for row in evaluations}
        else:
            entities=[item for dataset in record.snapshot.datasets for item in dataset.entities if item.department_id==unit_id]
            level=entities[0].department.department_level if entities else None
            values={}
            for dataset in record.snapshot.datasets:
                for entity in dataset.entities:
                    if entity.entity_kind!='child' or entity.department.department_level!=level:continue
                    values.setdefault(str(entity.department_id),{})[dataset.group_name]=(float(entity.api_score) if entity.api_score is not None else None)
                    if entity.department_id==unit_id:
                        groups[dataset.group_name]={'score':float(entity.api_score) if entity.api_score is not None else None,
                            'maximum':float(entity.api_max_score) if entity.api_max_score is not None else None}
            cohort={key:sum(items.values()) for key,items in values.items() if len(items)==6 and all(v is not None for v in items.values())}
            total=cohort.get(str(unit_id));peers=list(cohort.values())
            for key,items in (values.items() if include_peers else []):
                score=cohort.get(key)
                peer_scores[key]={'totalScore':score,'rank':1+sum(v>score+.005 for v in peers) if score is not None else None,'groups':items}
        if total is not None:rank=1+sum(score>total+.005 for score in peers)
        import hashlib
        days.append({'reportDate':record.report_date.isoformat(),'capturedAt':record.captured_at.isoformat(),
            'nationalCapturedAt':record.national_summary.captured_at.isoformat(),'totalScore':total,'rank':rank,
            'cohortSize':len(cohort),'cohortKey':hashlib.sha256('|'.join(sorted(cohort)).encode()).hexdigest(),'groups':groups,'peerScores':peer_scores})
    return {'days':days,'reportingPolicy':'previous-day-04:00-Asia/Ho_Chi_Minh','scope':'all'}
