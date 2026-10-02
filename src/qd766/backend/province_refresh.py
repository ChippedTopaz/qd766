from __future__ import annotations

from datetime import datetime, timedelta

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
