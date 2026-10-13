"""Resolve immutable, authorized daily reporting data; never collect or charge."""
from sqlalchemy import select
from fastapi import HTTPException
from .models import DailyObservation
from .dashboard import NATIONAL_GROUP_CODES,NATIONAL_GROUP_MAXIMUMS
from .daily_history import FIRST_VALID_REPORT_DATE

def saved_daily_record(db,root_id,period,report_date):
    in_period=report_date.year==period.year and (
        period.type=='year' or period.type=='month' and report_date.month==period.value or
        period.type=='quarter' and (report_date.month-1)//3+1==period.value)
    if report_date<FIRST_VALID_REPORT_DATE or not in_period:
        raise HTTPException(422,'Ngày dữ liệu không thuộc kỳ báo cáo được chọn.')
    record=db.scalar(select(DailyObservation).where(DailyObservation.root_department_id==root_id,
        DailyObservation.period_type==period.type,DailyObservation.year==period.year,
        DailyObservation.period_value==period.value,DailyObservation.report_date==report_date)
        .order_by(DailyObservation.captured_at.desc(),DailyObservation.id.desc()).limit(1))
    if record is None:raise HTTPException(404,'Chưa có bản dữ liệu của ngày được chọn. Không tự chuyển sang ngày khác.')
    return record

def daily_benchmarks(summary):
    result=[]
    for row in summary.response_data.get('evaluation',[]):
        result.append({'rootDepartmentId':row['departmentId'],'provinceName':row.get('departmentName',row['departmentId']),
            'totalScore':row.get('totalScore'),'totalMaximum':100,'capturedAt':summary.captured_at.isoformat(),
            'groups':{group:{'score':row.get('groupScores',{}).get(code),'maximum':NATIONAL_GROUP_MAXIMUMS[group],
                             'parameters':{},'metrics':{}} for group,code in NATIONAL_GROUP_CODES.items()}})
    return result
