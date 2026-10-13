"""Read saved reporting days for one authorized unit/group in one period."""
from datetime import timedelta
import math

from fastapi import HTTPException
from sqlalchemy import inspect, select, func
from sqlalchemy.orm import joinedload, selectinload

from .dashboard import GROUP_LABELS, NATIONAL_GROUP_CODES, _entity
from .daily_history import FIRST_VALID_REPORT_DATE
from .models import DailyObservation, Dataset, Department, Entity, Snapshot


def in_period(day, period):
    return day.year == period.year and (period.type == 'year' or
        period.type == 'month' and day.month == period.value or
        period.type == 'quarter' and (day.month - 1) // 3 + 1 == period.value)


def authorize_unit(db, root_id, unit_id):
    department = db.get(Department, unit_id)
    if department is None:
        raise HTTPException(404, 'Không tìm thấy cơ quan.')
    kind = 'root' if unit_id == root_id else 'child'
    membership = select(Entity.id).join(Dataset).join(Snapshot).where(
        Entity.department_id == unit_id, Entity.entity_kind == kind,
        Snapshot.root_department_id == root_id, Snapshot.scope == 'all',
        Snapshot.state == 'complete').limit(1)
    if db.scalar(membership) is None:
        raise HTTPException(403, 'Cơ quan không thuộc tỉnh được chọn.')
    return department


def comparison_payload(db, root_id, unit_id, period, group, current_date=None, baseline_date=None, *, department=None):
    if group not in GROUP_LABELS:
        raise HTTPException(422, 'Nhóm chỉ tiêu không hợp lệ.')
    for day in (current_date, baseline_date):
        if day is not None and not in_period(day, period):
            raise HTTPException(422, 'Hai ngày phải thuộc cùng kỳ báo cáo được chọn.')
    department = department or authorize_unit(db, root_id, unit_id)
    conditions = (DailyObservation.root_department_id == root_id,
        DailyObservation.period_type == period.type, DailyObservation.year == period.year,
        DailyObservation.period_value == period.value)
    dates = []
    table_available = inspect(db.bind).has_table('daily_observations')
    if table_available:
        # Only list dates with the selected group's actual entity. No raw history scan.
        dates = list(db.scalars(select(DailyObservation.report_date).join(
            Snapshot, DailyObservation.snapshot_id == Snapshot.id).join(Dataset).join(Entity).where(
            *conditions, DailyObservation.report_date >= FIRST_VALID_REPORT_DATE,
            Snapshot.root_department_id == root_id, Snapshot.scope == 'all', Snapshot.state == 'complete',
            Dataset.group_name == group, Entity.department_id == unit_id,
            Entity.entity_kind == ('root' if unit_id == root_id else 'child'))
            .distinct().order_by(DailyObservation.report_date.desc()).limit(366)))
    current = current_date or (dates[0] if dates else None)
    baseline = baseline_date or (current - timedelta(days=1) if current else None)
    if current is not None and baseline_date is not None and baseline_date >= current:
        raise HTTPException(422, 'Ngày làm mốc phải trước ngày đánh giá.')

    def sanitized_entity(entity):
        payload = _entity(entity, include_detail=True)
        payload['metrics'] = [{**{k: m.get(k) for k in (
            'code', 'name', 'numerator', 'denominator', 'ratio', 'apiScore', 'apiMaxScore')}, 'extras': {}}
            for m in payload['metrics'] if m['code'] != 'scoreDelta']
        payload['parameters'] = {k: v for k, v in payload['parameters'].items() if k != 'scoreDelta'
            and isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)}
        return payload

    def saved_day(day):
        empty = {'reportDate': day.isoformat() if day else None, 'entity': None,
                 'capturedAt': None, 'state': 'missing'}
        if day is None or not in_period(day, period):
            return {**empty, 'state': 'outside-period' if day else 'missing'}
        if day not in dates:
            return empty
        record = db.scalar(select(DailyObservation).where(*conditions, DailyObservation.report_date == day)
            .order_by(DailyObservation.captured_at.desc(), DailyObservation.id.desc()).limit(1))
        if record is None:
            return empty
        entity = db.scalar(select(Entity).join(Dataset).join(Snapshot).where(
            Snapshot.id == record.snapshot_id, Snapshot.root_department_id == root_id,
            Snapshot.scope == 'all', Snapshot.state == 'complete',
            Snapshot.period_type == period.type, Snapshot.year == period.year,
            Snapshot.period_value == period.value, Dataset.group_name == group,
            Entity.department_id == unit_id, Entity.entity_kind == ('root' if unit_id == root_id else 'child'))
            .options(joinedload(Entity.department), selectinload(Entity.metrics)).limit(1))
        if entity is None:
            return empty
        payload = sanitized_entity(entity)
        if unit_id == root_id:
            summary = record.national_summary
            row = next((r for r in summary.response_data.get('evaluation', [])
                if r.get('departmentId') == str(root_id)), None)
            score = row.get('groupScores', {}).get(NATIONAL_GROUP_CODES[group]) if row else None
            if score is not None:
                payload['apiScore'] = score
                payload['scoreSource'] = 'dvcqg-national-summary'
        return {'reportDate': day.isoformat(), 'capturedAt': record.captured_at.isoformat(),
                'entity': payload, 'state': 'available'}

    current_body, baseline_body = saved_day(current), saved_day(baseline)
    series = []
    if baseline is not None and current is not None:
        # One period caps the calendar interval at 366 days. Batch the intermediate
        # days rather than issuing one SQL/API request per bar.
        ranked = select(DailyObservation.report_date.label('day'), DailyObservation.snapshot_id,
            func.row_number().over(partition_by=DailyObservation.report_date,
                order_by=(DailyObservation.captured_at.desc(), DailyObservation.id.desc())).label('position')).where(
            *conditions, DailyObservation.report_date > baseline, DailyObservation.report_date < current,
            DailyObservation.report_date >= FIRST_VALID_REPORT_DATE).subquery()
        records = dict(db.execute(select(ranked.c.day, ranked.c.snapshot_id).where(ranked.c.position == 1)).all()) if table_available else {}
        entities = {}
        if records:
            rows = db.execute(select(Entity, Dataset.snapshot_id).join(Dataset).join(Snapshot).where(
                Snapshot.id.in_(list(set(records.values()))), Snapshot.root_department_id == root_id,
                Snapshot.scope == 'all', Snapshot.state == 'complete', Snapshot.period_type == period.type,
                Snapshot.year == period.year, Snapshot.period_value == period.value,
                Dataset.group_name == group, Entity.department_id == unit_id,
                Entity.entity_kind == ('root' if unit_id == root_id else 'child'))
                .options(joinedload(Entity.department), selectinload(Entity.metrics))).all()
            entities = {snapshot_id: sanitized_entity(entity) for entity, snapshot_id in rows}
        day = baseline
        while day <= current:
            if day == baseline:
                series.append(baseline_body)
            elif day == current:
                series.append(current_body)
            else:
                entity = entities.get(records.get(day))
                series.append({'reportDate': day.isoformat(), 'capturedAt': None,
                    'entity': entity, 'state': 'available' if entity is not None else 'missing'})
            day += timedelta(days=1)

    return {'scope': 'all', 'group': group, 'unitId': str(unit_id), 'unitName': department.name,
            'availableDates': [d.isoformat() for d in dates],
            'current': current_body, 'baseline': baseline_body, 'series': series}
