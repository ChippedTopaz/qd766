from __future__ import annotations

from datetime import timezone

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from qd766.national_summary import GROUP_CODES, GROUP_COUNT, NationalSummaryCapture
from qd766.periods import PeriodSelection

from .models import NationalSummarySnapshot


def _record_recapture(session: Session, existing: NationalSummarySnapshot, capture: NationalSummaryCapture) -> None:
    previous = existing.captured_at
    previous = previous if previous.tzinfo else previous.replace(tzinfo=timezone.utc)
    current = capture.captured_at
    current = current if current.tzinfo else current.replace(tzinfo=timezone.utc)
    if current > previous:
        # Same content is still a successful new observation. Keep created_at
        # and the content hash/version; never fabricate a time without a capture.
        existing.captured_at = current
        session.flush()


def store_national_summary(
    session: Session, capture: NationalSummaryCapture
) -> tuple[NationalSummarySnapshot, bool]:
    period_value = capture.period.value
    summary_key = ":".join(
        [
            capture.period.type,
            str(capture.period.year),
            str(period_value or 0),
            capture.raw_sha256,
        ]
    )
    existing = session.scalar(
        select(NationalSummarySnapshot).where(
            NationalSummarySnapshot.summary_key == summary_key
        )
    )
    if existing is not None:
        _record_recapture(session, existing, capture)
        return existing, False
    snapshot = NationalSummarySnapshot(
        summary_key=summary_key,
        period_type=capture.period.type,
        year=capture.period.year,
        period_value=period_value,
        department_type="ADMINISTRATIVE_UNIT",
        province_count=len(capture.response_data["evaluation"]),
        completeness_state="complete",
        group_count=GROUP_COUNT,
        group_codes=sorted(GROUP_CODES),
        raw_sha256=capture.raw_sha256,
        request_payload=capture.request_payload,
        response_data=capture.response_data,
        captured_at=capture.captured_at,
    )
    try:
        with session.begin_nested():
            session.add(snapshot)
            session.flush()
    except IntegrityError:
        existing = session.scalar(
            select(NationalSummarySnapshot).where(
                NationalSummarySnapshot.summary_key == summary_key
            )
        )
        if existing is None:
            raise
        _record_recapture(session, existing, capture)
        return existing, False
    return snapshot, True


def latest_national_summary(
    session: Session, period: PeriodSelection
) -> NationalSummarySnapshot | None:
    statement = (
        select(NationalSummarySnapshot)
        .where(
            NationalSummarySnapshot.period_type == period.type,
            NationalSummarySnapshot.year == period.year,
            NationalSummarySnapshot.completeness_state == "complete",
            NationalSummarySnapshot.group_count == GROUP_COUNT,
        )
        .order_by(NationalSummarySnapshot.captured_at.desc())
        .limit(1)
    )
    statement = (
        statement.where(NationalSummarySnapshot.period_value.is_(None))
        if period.value is None
        else statement.where(NationalSummarySnapshot.period_value == period.value)
    )
    return session.scalar(statement)
