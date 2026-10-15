"""Bounded, score-only daily ranking view. No collection, metrics or wallet writes."""
from datetime import date, timedelta
from decimal import Decimal
import math
from sqlalchemy import select, inspect
from .models import DailyObservation, Dataset, Entity, Department, NationalSummarySnapshot
from .daily_history import FIRST_VALID_REPORT_DATE
from .dashboard import NATIONAL_GROUP_CODES


def number(value):
    return float(value) if not isinstance(value, bool) and isinstance(value, (int, float, Decimal)) and math.isfinite(value) else None


def ranking_history(db, root_id, unit_id, period, report_date=None, baseline_date=None):
    empty = {'current': None, 'baseline': None}
    if not inspect(db.bind).has_table('daily_observations'):
        return empty
    conditions = (DailyObservation.root_department_id == root_id,
        DailyObservation.period_type == period.type, DailyObservation.year == period.year,
        DailyObservation.period_value == period.value,
        DailyObservation.report_date >= FIRST_VALID_REPORT_DATE,
        DailyObservation.report_date >= date(period.year, 1, 1),
        DailyObservation.report_date <= date(period.year, 12, 31))
    def record(day=None):
        query = select(DailyObservation).where(*conditions)
        if day is not None:
            query = query.where(DailyObservation.report_date == day)
        return db.scalar(query.order_by(DailyObservation.report_date.desc(),
            DailyObservation.captured_at.desc(), DailyObservation.id.desc()).limit(1))
    current = record(report_date)
    if current is None:
        return empty
    if baseline_date is not None and baseline_date>=current.report_date:
        from fastapi import HTTPException
        raise HTTPException(422,'Ngày đối chiếu phải trước ngày dữ liệu.')
    baseline = record(baseline_date or current.report_date - timedelta(days=1))
    department = db.get(Department, unit_id)
    level = department.department_level if department else None

    def pack(saved):
        if saved is None:
            return None
        rows = []
        if unit_id == root_id:
            summary = db.get(NationalSummarySnapshot, saved.national_summary_id)
            for item in summary.response_data.get('evaluation', []) if summary else []:
                rows.append({'id': item['departmentId'], 'name': item.get('departmentName', item['departmentId']),
                    'total': number(item.get('totalScore')),
                    'groups': {g: number(item.get('groupScores', {}).get(code)) for g, code in NATIONAL_GROUP_CODES.items()}})
        else:
            # Select scalar score columns only; never load raw parameters or indicator metrics.
            values = db.execute(select(Entity.department_id, Department.name,
                Dataset.group_name, Entity.api_score).join(Dataset, Entity.dataset_id == Dataset.id)
                .join(Department, Entity.department_id == Department.id).where(
                    Dataset.snapshot_id == saved.snapshot_id, Entity.entity_kind == 'child',
                    Department.department_level == level))
            entities = {}
            for ident, name, group, score in values:
                row = entities.setdefault(str(ident), {'id': str(ident), 'name': name or str(ident), 'groups': {}})
                row['groups'][group] = number(score)
            for row in entities.values():
                scores = [row['groups'].get(g) for g in NATIONAL_GROUP_CODES]
                row['total'] = round(sum(scores), 2) if all(s is not None for s in scores) else None
                rows.append(row)
        return {'reportDate': saved.report_date.isoformat(), 'capturedAt': saved.captured_at.isoformat(), 'rows': rows}
    return {'current': pack(current), 'baseline': pack(baseline)}
