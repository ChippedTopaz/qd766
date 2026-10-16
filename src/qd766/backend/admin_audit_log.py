"""Admin audit projections; never return credentials or unbounded raw payloads."""
import uuid
from sqlalchemy import select, func, or_
from fastapi import HTTPException
from .models import AdminAudit, UserAccount, Department
from .admin_log_history import date_bounds, paging

SAFE_KEYS = {'accountId', 'registrationId', 'invitationId', 'linkId', 'alertId', 'questionId',
    'noticeId', 'publication',
    'active', 'provinceId', 'unitId', 'accessTier', 'version', 'revision', 'group', 'groupId',
    'count', 'duplicates', 'state', 'canCollect', 'amount', 'reason', 'creditSource',
    'startsAt', 'endsAt', 'trialStartsAt', 'trialEndsAt', 'email', 'before', 'after',
    'enabled', 'days', 'maxRegistrations', 'deletedAnswers', 'affectedAccounts', 'clearedPending'}


def safe_details(value, depth=0):
    if depth > 5:
        return '…'
    if isinstance(value, dict):
        return {k: safe_details(v, depth+1) for k, v in value.items() if k in SAFE_KEYS}
    if isinstance(value, list):
        return [safe_details(v, depth+1) for v in value[:50]]
    if isinstance(value, str):
        return value[:1000]
    return value if value is None or isinstance(value, (int, float, bool)) else str(value)[:200]


def account_ids(rows):
    ids = {r.actor_id for r in rows}
    for row in rows:
        try: ids.add(uuid.UUID(str(row.details.get('accountId'))))
        except (ValueError, TypeError): pass
    return ids


def payloads(db, rows, *, detail=False):
    users = {str(u.id): u for u in db.scalars(select(UserAccount).where(UserAccount.id.in_(account_ids(rows))))} if rows else {}
    result = []
    for row in rows:
        actor = users.get(str(row.actor_id))
        target = users.get(str(row.details.get('accountId')))
        entity = next((str(row.details[k]) for k in ('email', 'registrationId', 'invitationId', 'linkId', 'questionId', 'alertId', 'group') if row.details.get(k) is not None), 'Cấu hình hệ thống')
        item = {'id': str(row.id), 'action': row.action, 'at': row.created_at.isoformat(),
            'actorId': str(row.actor_id), 'actor': actor.display_name if actor else 'Quản trị',
            'actorEmail': actor.email if actor else None,
            'target': target.display_name if target else entity[:320], 'targetEmail': target.email if target else None}
        if detail:
            item['details'] = safe_details(row.details)
            # Resolve labels for before/after assignment values without exposing other accounts.
            ids = []
            for values in (row.details, row.details.get('before', {}), row.details.get('after', {})):
                if not isinstance(values, dict): continue
                for key in ('provinceId', 'unitId'):
                    try: ids.append(uuid.UUID(str(values.get(key))))
                    except (ValueError, TypeError): pass
            item['departmentNames'] = {str(k): v for k, v in db.execute(select(Department.id, Department.name).where(Department.id.in_(ids)))} if ids else {}
        result.append(item)
    return result


def audit_page(db, page, start, end, actor_id, action, search):
    lower, upper = date_bounds(start, end)
    query = select(AdminAudit)
    if lower: query = query.where(AdminAudit.created_at >= lower)
    if upper: query = query.where(AdminAudit.created_at < upper)
    if actor_id: query = query.where(AdminAudit.actor_id == actor_id)
    if action: query = query.where(AdminAudit.action == action)
    if search.strip():
        pattern = '%' + search.strip().replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_') + '%'
        matches = select(UserAccount.id).where(or_(UserAccount.display_name.ilike(pattern, escape='\\'), UserAccount.email.ilike(pattern, escape='\\')))
        # Only account identity fields are searchable, not secret-bearing raw audit JSON.
        ids = [str(i) for i in db.scalars(matches)]
        query = query.where(or_(AdminAudit.actor_id.in_(matches),
            AdminAudit.details['accountId'].as_string().in_(ids),
            AdminAudit.details['email'].as_string().ilike(pattern, escape='\\')))
    total = db.scalar(select(func.count()).select_from(query.subquery()))
    page, offset = paging(page, total)
    rows = list(db.scalars(query.order_by(AdminAudit.created_at.desc(), AdminAudit.id.desc()).offset(offset).limit(10)))
    actors = db.execute(select(UserAccount.id, UserAccount.display_name).join(AdminAudit, AdminAudit.actor_id == UserAccount.id).distinct().order_by(UserAccount.display_name)).all()
    return {'items': payloads(db, rows), 'total': total, 'page': page, 'pageSize': 10,
        'actors': [{'id': str(k), 'name': name} for k, name in actors],
        'actions': list(db.scalars(select(AdminAudit.action).distinct().order_by(AdminAudit.action)))}


def audit_detail(db, identifier):
    item = db.get(AdminAudit, identifier)
    if item is None: raise HTTPException(404, 'Không tìm thấy nhật ký quản trị.')
    return payloads(db, [item], detail=True)[0]
