"""Daily reuse boundary for unfinished TTHC periods, in Vietnam time."""
from datetime import datetime, timedelta, timezone
from qd766.periods import PeriodSelection

VIETNAM = timezone(timedelta(hours=7))

def daily_cutoff(kind, year, value, *, now=None):
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    today = now.astimezone(VIETNAM).date()
    start, end = PeriodSelection(kind, year, value).date_range()
    if not start <= today.isoformat() <= end:
        return None
    return datetime.combine(today, datetime.min.time(), VIETNAM).astimezone(timezone.utc)

def fresh_entitlement(statement, cutoff, *, request_model, snapshot_model):
    if cutoff is None:
        return statement
    from sqlalchemy import or_, select
    # Active requests still deduplicate; ready data expires at Vietnam midnight.
    fresh_ids = select(snapshot_model.id).where(snapshot_model.created_at >= cutoff)
    return statement.where(or_(request_model.state.in_(("reserved", "waiting")),
                               request_model.snapshot_id.in_(fresh_ids)))
