"""Read-only, group-scoped comparison evidence; strict cohort and ±20% volume gate."""
from datetime import datetime,timezone
from zoneinfo import ZoneInfo
from statistics import median
from sqlalchemy import select,func
from sqlalchemy.orm import selectinload
from qd766.periods import PeriodSelection
from .models import Snapshot,Dataset,Entity
from .analysis_rules import number,LABELS,ACTIONS
from .credit_wallet import utc

PROGRESS='dvc-progress-tree'

def received(parameters):
    value=number(parameters.get('totalReceived'))
    if value is None or value<0 or int(value)!=value:return None
    ontime=number(parameters.get('totalOnTime'));overdue=number(parameters.get('totalOverdue'))
    if ontime is not None and overdue is not None and (min(ontime,overdue)<0 or ontime+overdue!=value):return None
    return int(value)

def within_volume(target,other):
    # Integer arithmetic includes both exact boundaries without float rounding drift.
    return target is not None and target>0 and other is not None and 4*target<=5*other<=6*target

def previous_periods(snapshot):
    year=snapshot.year;value=snapshot.period_value
    for _ in range(3):
        if snapshot.period_type=='year':year-=1
        else:
            value-=1
            if value==0:year-=1;value=12 if snapshot.period_type=='month' else 4
        yield PeriodSelection(snapshot.period_type,year,value)

def period_label(kind,year,value):
    return f'Tháng {value}/{year}' if kind=='month' else f'Quý {value}/{year}' if kind=='quarter' else f'Năm {year}'

def group_data(dataset,entity,snapshot):
    return {'id':dataset.group_name,'score':float(entity.api_score) if entity.api_score is not None else None,
        'maximum':float(entity.api_max_score) if entity.api_max_score is not None else None,
        'formulaVersion':dataset.details.get('formulaVersion',snapshot.policy.get('formulaVersion')),
        'parameters':{key:value for key,value in entity.parameters.items() if number(value) is not None},
        'metrics':[{'code':m.code,'name':m.name,'numerator':float(m.numerator) if m.numerator is not None else None,
            'denominator':float(m.denominator) if m.denominator is not None else None,
            'score':float(m.api_score) if m.api_score is not None else None,
            'maximum':float(m.api_max_score) if m.api_max_score is not None else None} for m in entity.metrics]}

def compatible(current,before):
    if number(before.get('score')) is None or current.get('maximum')!=before.get('maximum'):return False
    left=current.get('formulaVersion');right=before.get('formulaVersion')
    if (left is not None or right is not None) and left!=right:return False
    limits=lambda g:sorted((m['code'],m.get('maximum')) for m in g.get('metrics',[]))
    return limits(current)==limits(before)

def comparison_evidence(db,snapshot,unit_id,groups):
    keys=[group['id'] for group in groups];current={group['id']:group for group in groups}
    output={key:{'periods':[],'peers':{'count':0,'scope':'same-province','volumeTolerancePercent':20}} for key in keys}
    # Exact previous periods, never substitute a farther period when a gap exists.
    for period in previous_periods(snapshot):
        before=db.scalar(select(Snapshot).where(Snapshot.root_department_id==snapshot.root_department_id,
            Snapshot.scope=='all',Snapshot.state=='complete',Snapshot.period_type==period.type,
            Snapshot.year==period.year,Snapshot.period_value==period.value,Snapshot.created_at<=snapshot.created_at)
            .order_by(Snapshot.created_at.desc(),Snapshot.id.desc()).limit(1))
        records={}
        if before:
            pairs=db.execute(select(Dataset,Entity).join(Entity).where(Dataset.snapshot_id==before.id,
                Dataset.group_name.in_(keys),Entity.department_id==unit_id)
                .options(selectinload(Entity.metrics))).all()
            records={dataset.group_name:group_data(dataset,entity,before) for dataset,entity in pairs}
        for key in keys:
            record=records.get(key)
            allowed=record is not None and compatible(current[key],record)
            row={'periodType':period.type,'year':period.year,'periodValue':period.value,
                'label':period_label(period.type,period.year,period.value),'available':record is not None,
                'comparable':allowed,'capturedAt':utc(before.created_at).isoformat() if before else None,
                'group':record if allowed else None,'delta':current[key]['score']-record['score'] if allowed else None,
                'reason':None if allowed else 'Thiếu dữ liệu kỳ/cơ quan hoặc thang điểm, cấu trúc chỉ tiêu, phiên bản công thức không tương thích.'}
            output[key]['periods'].append(row)
    target=db.scalar(select(Entity).join(Dataset).where(Dataset.snapshot_id==snapshot.id,
        Dataset.group_name==PROGRESS,Entity.department_id==unit_id).options(selectinload(Entity.department)))
    volume=received(target.parameters) if target else None
    if not target or not volume:
        for value in output.values():value['peers']['reason']='Chưa có tổng hồ sơ tiếp nhận hợp lệ, khác không; không thể lọc cơ quan tương đồng.'
        return output
    level=target.department.department_level
    if target.entity_kind=='child' and level not in ('COMMUNE','PROVINCE'):
        for value in output.values():value['peers']['reason']='Chưa xác định được cấp cơ quan; không so sánh khác cấp hoặc suy đoán theo tên.'
        return output
    if target.entity_kind=='root':
        # Province-to-province: only root aggregates from the same capture day.
        local_day=utc(snapshot.created_at).astimezone(ZoneInfo('Asia/Ho_Chi_Minh')).date()
        start=datetime.combine(local_day,datetime.min.time(),ZoneInfo('Asia/Ho_Chi_Minh')).astimezone(timezone.utc)
        ranked=select(Snapshot.id,func.row_number().over(partition_by=Snapshot.root_department_id,
            order_by=(Snapshot.created_at.desc(),Snapshot.id.desc())).label('position')).where(
            Snapshot.scope=='all',Snapshot.state=='complete',Snapshot.period_type==snapshot.period_type,
            Snapshot.year==snapshot.year,Snapshot.period_value==snapshot.period_value,
            Snapshot.created_at>=start,Snapshot.created_at<=snapshot.created_at).subquery()
        snapshot_ids=select(ranked.c.id).where(ranked.c.position==1)
        scope='province-roots-same-capture-day'
    else:snapshot_ids=[snapshot.id];scope='same-province'
    pairs=db.execute(select(Dataset,Entity,Snapshot.policy).join(Entity).join(Snapshot,Dataset.snapshot_id==Snapshot.id).where(Dataset.snapshot_id.in_(snapshot_ids),
        Dataset.group_name.in_(list(set(keys+[PROGRESS]))),Entity.entity_kind==target.entity_kind)
        .options(selectinload(Entity.department))).all()
    inventory={}
    for dataset,entity,policy in pairs:
        if entity.department_id==unit_id:continue
        if target.entity_kind=='child' and entity.department.department_level!=level:continue
        row=inventory.setdefault(entity.department_id,{})
        row[dataset.group_name]=(entity,dataset.details.get('formulaVersion',policy.get('formulaVersion')))
    for key,value in output.items():
        scores=[]
        for row in inventory.values():
            candidate=row.get(key);progress=row.get(PROGRESS)
            if not candidate or not progress or not within_volume(volume,received(progress[0].parameters)):continue
            entity,version=candidate
            current_version=current[key].get('formulaVersion')
            if (version is not None or current_version is not None) and version!=current_version:continue
            if entity.api_score is None or entity.api_max_score is None or float(entity.api_max_score)!=current[key]['maximum']:continue
            score=float(entity.api_score)
            if number(score) is not None:scores.append(score)
        peer=value['peers'];peer.update(scope=scope,level='PROVINCE_TOTAL' if target.entity_kind=='root' else level,
            targetReceived=volume,minimumReceived=(4*volume+4)//5,maximumReceived=(6*volume)//5,count=len(scores))
        # Provider receives aggregate benchmarks only, never another agency's raw parameters,
        # identities or metric details. Agency-scoped users retain their existing access.
        if scores:
            peer.update(medianScore=median(scores),meanScore=sum(scores)/len(scores),minimumScore=min(scores),maximumScore=max(scores),
                targetRank=1+sum(score>current[key]['score']+.005 for score in scores),cohortSize=len(scores)+1,
                gapToMedian=current[key]['score']-median(scores))
        else:peer['reason']='Không có cơ quan cùng cấp, cùng kỳ, cùng thang điểm và số hồ sơ trong khoảng ±20%.'
    return output

def add_comparison_findings(cards,groups,comparisons):
    """Every purchased group gets an overview; comparison numbers stay server-grounded."""
    result=list(cards)
    for group in groups:
        key=group['id'];comparison=comparisons[key]
        if not any(card['groupId']==key for card in result):
            result.append({'id':key+':overview','groupId':key,'kind':'strength' if group['score']/group['maximum']>=.8 else 'priority',
                'title':'Đánh giá '+LABELS[key],'evidence':f"{group['score']:.2f}/{group['maximum']:.2f} điểm trong kỳ đang chọn.",'action':ACTIONS[key]})
        immediate=comparison['periods'][0];peer=comparison['peers'];notes=[]
        if immediate['comparable']:
            notes.append(f"So với {immediate['label']}: {immediate['delta']:+.2f} điểm.")
        else:notes.append('Chưa đủ căn cứ so sánh với kỳ liền trước.')
        if peer['count']:
            notes.append(f"{peer['count']} cơ quan cùng cấp có {peer['minimumReceived']}–{peer['maximumReceived']} hồ sơ; trung vị {peer['medianScore']:.2f} điểm; chênh {peer['gapToMedian']:+.2f} điểm.")
        else:notes.append(peer['reason'])
        kind='priority' if (immediate['comparable'] and immediate['delta']<-.005) or peer.get('gapToMedian',0)<-.005 else 'strength'
        # Missing comparisons do not become a fabricated positive conclusion.
        if immediate['comparable'] or peer['count']:
            result.append({'id':key+':comparison','groupId':key,'kind':kind,'title':'Đối chiếu '+LABELS[key],
                'evidence':' '.join(notes),'action':'Đối chiếu kỳ liền trước và chuẩn cơ quan cùng cấp có số hồ sơ tương đồng. Kết hợp chỉ tiêu thành phần để đề xuất hành động; khác quy mô hoặc kỳ chưa kết thúc không chứng minh nguyên nhân.'})
    return result
