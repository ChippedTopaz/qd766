"""Read projections: one notice per logical run, original alert evidence/reviews retained."""
from sqlalchemy import select,func,case,cast,String
from .models import SourceMonitorAlert as A
from .admin_log_history import date_bounds,paging


def batch_key():
    # Never infer old runs from timestamps: old alerts may span several runs.
    return func.coalesce(A.details['batch']['id'].as_string(),'legacy:'+cast(A.id,String))


def batch_query():
    key=batch_key()
    return select(key.label('id'),func.max(A.updated_at).label('updatedAt'),
        func.min(A.created_at).label('createdAt'),func.count().label('contentCount'),
        func.sum(func.coalesce(A.details['changeCount'].as_integer(),0)).label('changeCount'),
        func.sum(case((A.read_at.is_(None)&A.resolved_at.is_(None),1),else_=0)).label('unreadCount'),
        func.sum(case((A.resolved_at.is_(None),1),else_=0)).label('openCount'),
        *[func.sum(case((A.kind==kind,1),else_=0)).label(kind) for kind in ('structure','closed-period','check-failed')],
        func.max(A.details['batch']['label'].as_string()).label('label'),
        func.max(A.details['batch']['day'].as_string()).label('day')).group_by(key)


def batch_list(db,page,state,kind,from_date,to_date):
    rows=batch_query().subquery();predicates=[]
    if state=='open':predicates.append(rows.c.openCount>0)
    if state=='unread':predicates.append(rows.c.unreadCount>0)
    if state=='resolved':predicates.append(rows.c.openCount==0)
    if kind:predicates.append(rows.c[kind]>0)
    lower,upper=date_bounds(from_date,to_date)
    if lower:predicates.append(rows.c.updatedAt>=lower)
    if upper:predicates.append(rows.c.updatedAt<upper)
    total=db.scalar(select(func.count()).select_from(rows).where(*predicates))
    page,offset=paging(page,total)
    items=[batch_payload(dict(r)) for r in db.execute(select(rows).where(*predicates)
        .order_by(rows.c.updatedAt.desc(),rows.c.id).offset(offset).limit(10)).mappings()]
    unread=db.scalar(select(func.count()).select_from(rows).where(rows.c.unreadCount>0))
    open_count=db.scalar(select(func.count()).select_from(rows).where(rows.c.openCount>0))
    return {'items':items,'total':total,'page':page,'pageSize':10,'unread':unread,'openCount':open_count,'grouped':True}


def batch_payload(row):
    row['kinds']={kind:row.pop(kind) for kind in ('structure','closed-period','check-failed')}
    row['title']='Thay đổi nguồn dữ liệu' if row['label'] else 'Cảnh báo lịch sử · chưa lưu mã đợt'
    row['label']=row['label'] or 'Giữ nguyên cảnh báo cũ'
    for key in ('updatedAt','createdAt'):row[key]=row[key].isoformat()
    return row


def batch_summary(db,identifier):
    row=db.execute(batch_query().where(batch_key()==identifier)).mappings().first()
    return batch_payload(dict(row)) if row and row['contentCount'] else None
