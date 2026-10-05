from __future__ import annotations

from datetime import datetime, timedelta, timezone

from qd766.periods import PeriodSelection


def current_detail_periods(now: datetime) -> list[PeriodSelection]:
    """Return current periods in first-run priority order."""

    return [
        PeriodSelection("year", now.year),
        PeriodSelection("month", now.year, now.month),
        PeriodSelection("quarter", now.year, (now.month - 1) // 3 + 1),
    ]


def choose_detail_refresh_period(
    now: datetime,
    latest_completed: dict[tuple[str, int, int | None], datetime],
    *,
    interval: timedelta = timedelta(hours=72),
) -> PeriodSelection | None:
    """Choose the stalest due period while staggering expensive detail batches."""

    cutoff = now - interval
    due: list[tuple[datetime | None, int, PeriodSelection]] = []
    for priority, period in enumerate(current_detail_periods(now)):
        completed = latest_completed.get((period.type, period.year, period.value))
        if completed is None or completed <= cutoff:
            due.append((completed, priority, period))
    if not due:
        return None
    # Never-completed periods come first in year/month/quarter order. Afterwards
    # refresh the period whose last successful national detail batch is oldest.
    due.sort(
        key=lambda item: (
            item[0] is not None,
            item[0] or datetime.min.replace(tzinfo=now.tzinfo),
            item[1],
        )
    )
    return due[0][2]

VIETNAM = timezone(timedelta(hours=7))

def daily_fresh_after(now: datetime) -> datetime:
    """Daily 02:00 deadline with one hour to finish/retry; never an hourly TTL."""
    local=now.replace(tzinfo=VIETNAM) if now.tzinfo is None else now.astimezone(VIETNAM)
    boundary=local.replace(hour=2,minute=0,second=0,microsecond=0)
    return boundary-timedelta(days=1) if local<boundary+timedelta(hours=1) else boundary

def daily_refresh_candidates(now: datetime, *, start_year: int = 2026) -> list[PeriodSelection]:
    """Open periods plus closed periods that may need a post-close capture."""
    now = now.replace(tzinfo=VIETNAM) if now.tzinfo is None else now.astimezone(VIETNAM)
    candidates = current_detail_periods(now)
    for year in range(start_year, now.year + 1):
        months = now.month - 1 if year == now.year else 12
        quarters = (now.month - 1) // 3 if year == now.year else 4
        candidates += [PeriodSelection('month', year, v) for v in range(1, months + 1)]
        candidates += [PeriodSelection('quarter', year, v) for v in range(1, quarters + 1)]
        if year < now.year:
            candidates.append(PeriodSelection('year', year))
    return candidates

def refresh_cutoff(period: PeriodSelection, now: datetime) -> datetime:
    """Daily open-period freshness; closed periods require at least one later capture."""
    local = now.replace(tzinfo=VIETNAM) if now.tzinfo is None else now.astimezone(VIETNAM)
    _, end = period.date_range()
    end_date = datetime.fromisoformat(end).replace(tzinfo=VIETNAM) + timedelta(days=1)
    if local >= end_date:
        return end_date
    return local.replace(hour=0, minute=0, second=0, microsecond=0)

def due_daily_periods(now: datetime, latest_completed: dict, *, start_year: int = 2026):
    due=[]
    for period in daily_refresh_candidates(now,start_year=start_year):
        captured=latest_completed.get((period.type,period.year,period.value))
        if captured is not None and captured.tzinfo is None:
            captured=captured.replace(tzinfo=timezone.utc)
        if captured is None or captured < refresh_cutoff(period,now):
            due.append(period)
    return due
