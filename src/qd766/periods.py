"""Translate the user-facing month/quarter/year choice into endpoint payloads."""

from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date
from typing import Literal

PeriodType = Literal["month", "quarter", "year"]


@dataclass(frozen=True)
class PeriodSelection:
    """A reporting period exposed by the product UI.

    ``value`` is required for month (1..12) and quarter (1..4), and must be
    omitted for year. Free-form dates are deliberately not part of this model.
    """

    type: PeriodType
    year: int
    value: int | None = None

    def __post_init__(self) -> None:
        if self.type not in ("month", "quarter", "year"):
            raise ValueError(f"Unsupported period type: {self.type}")
        if self.year < 2000 or self.year > 9999:
            raise ValueError("year must be between 2000 and 9999")
        if self.type == "month" and self.value not in range(1, 13):
            raise ValueError("month value must be between 1 and 12")
        if self.type == "quarter" and self.value not in range(1, 5):
            raise ValueError("quarter value must be between 1 and 4")
        if self.type == "year" and self.value is not None:
            raise ValueError("year period must not have a value")

    def date_range(self) -> tuple[str, str]:
        """Return the inclusive dates required by handling-satisfaction."""

        if self.type == "year":
            start_month, end_month = 1, 12
        elif self.type == "quarter":
            start_month = (self.value - 1) * 3 + 1  # type: ignore[operator]
            end_month = start_month + 2
        else:
            start_month = end_month = self.value  # type: ignore[assignment]
        end_day = calendar.monthrange(self.year, end_month)[1]
        return (
            date(self.year, start_month, 1).isoformat(),
            date(self.year, end_month, end_day).isoformat(),
        )

    def validate_collectable(self, as_of: date | None = None) -> None:
        """Reject periods that the public QĐ766 UI does not expose yet.

        Month data is available only after that calendar month has ended. The
        UI allows the current quarter and current year, but not a future
        quarter or year. Keeping this check at the collection boundary lets
        historical fixtures remain readable without treating them as live
        collection requests.
        """

        current = as_of or date.today()
        if self.year > current.year:
            raise ValueError("reporting year is not available yet")
        if self.year < current.year:
            return
        if self.type == "month" and self.value >= current.month:  # type: ignore[operator]
            raise ValueError("monthly data is available only after the month has ended")
        if self.type == "quarter":
            current_quarter = (current.month - 1) // 3 + 1
            if self.value > current_quarter:  # type: ignore[operator]
                raise ValueError("future quarter data is not available")


ENDPOINTS = {
    "transparency": (200, "formalityId"),
    "handling-satisfaction": (200, None),
    "dossier-digitized": (200, "formalityID"),
    "dvc-progress-tree": (100, "formalityId"),
    "provide-online-tree": (200, "formalityId"),
    "formality-online-payment-tree": (100, "formalityId"),
}


def build_evaluation_payload(
    group: str,
    period: PeriodSelection,
    root_department_id: str,
    formality_id: str | None = None,
) -> dict[str, object]:
    """Build the exact payload shape observed in the M0 fixtures."""

    try:
        page_size, formality_key = ENDPOINTS[group]
    except KeyError as exc:
        raise ValueError(f"Unsupported evaluation group: {group}") from exc

    payload: dict[str, object] = {
        "rootDepartmentId": root_department_id,
        "currentPage": 1,
        "pageSize": page_size,
    }
    if group == "handling-satisfaction":
        if formality_id is not None:
            raise ValueError("handling-satisfaction does not support formality drill-down")
        payload["fromDate"], payload["toDate"] = period.date_range()
        return payload

    payload.update(timeType=period.type, year=period.year)
    if period.type != "year":
        payload[period.type] = period.value
    if formality_id is not None:
        payload[formality_key] = formality_id
    return payload
