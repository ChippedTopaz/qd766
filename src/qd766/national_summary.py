"""Collect and validate the nationwide QĐ766 summary in one request."""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from numbers import Real

from qd766.collection import (
    CollectionError,
    RateLimitStop,
    SafetyStop,
    Transport,
    TransportResponse,
)
from qd766.periods import PeriodSelection

SERVICE_RESULTS_URL = (
    "https://dichvucong.gov.vn/api/v1/reporting/evaluation/service-results"
)
GROUP_CODES = {"CKMB", "TDGQ", "CLGQ", "TTTT", "MDHL", "MDSH"}


@dataclass(frozen=True)
class NationalSummaryCapture:
    period: PeriodSelection
    request_payload: dict[str, object]
    response_data: dict
    raw_sha256: str
    captured_at: datetime


def build_national_summary_payload(period: PeriodSelection) -> dict[str, object]:
    period.validate_collectable()
    payload: dict[str, object] = {
        "timeType": period.type,
        "year": period.year,
        "departmentType": "ADMINISTRATIVE_UNIT",
    }
    if period.type in {"month", "quarter"}:
        payload[period.type] = period.value
    return payload


def collect_national_summary(
    period: PeriodSelection,
    transport: Transport,
    *,
    captured_at: datetime | None = None,
) -> NationalSummaryCapture:
    payload = build_national_summary_payload(period)
    response = transport.post_json(SERVICE_RESULTS_URL, payload)
    _guard_response(response)
    try:
        envelope = json.loads(response.body)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise CollectionError("National summary response is not valid JSON") from error
    data = envelope.get("data") if isinstance(envelope, dict) else None
    if (
        not isinstance(envelope, dict)
        or envelope.get("code") != "OK"
        or not isinstance(data, dict)
    ):
        raise CollectionError("Unexpected national summary response envelope")
    _validate_data(data)
    return NationalSummaryCapture(
        period=period,
        request_payload=payload,
        response_data=data,
        raw_sha256=hashlib.sha256(response.body).hexdigest(),
        captured_at=captured_at or datetime.now(timezone.utc),
    )


def _guard_response(response: TransportResponse) -> None:
    if response.status in {403, 429}:
        raise RateLimitStop(f"Stopped on HTTP {response.status} for national summary")
    content_type = (response.contentType or "").lower()
    rejection_body = response.body[:4096].lower()
    if (
        "text/html" in content_type
        or b"request rejected" in rejection_body
        or b"access denied" in rejection_body
    ):
        fingerprint = hashlib.sha256(response.body).hexdigest()[:16]
        raise SafetyStop(
            "Stopped on rejection/HTML national summary response "
            f"(HTTP {response.status}; content-type={content_type or 'unknown'}; "
            f"body-sha256={fingerprint})"
        )
    if response.status not in {200, 201}:
        raise CollectionError(f"HTTP {response.status} for national summary")


def _validate_data(data: dict) -> None:
    overview = data.get("overview")
    evaluation = data.get("evaluation")
    if not isinstance(overview, dict) or overview.get("departmentName") != "Cả nước":
        raise CollectionError("National summary overview is invalid")
    if not isinstance(evaluation, list) or len(evaluation) != 34:
        raise CollectionError("National summary must contain exactly 34 provinces")
    department_ids: set[uuid.UUID] = set()
    for item in evaluation:
        if not isinstance(item, dict):
            raise CollectionError("National summary province row is invalid")
        try:
            department_id = uuid.UUID(str(item.get("departmentId")))
        except (ValueError, TypeError, AttributeError) as error:
            raise CollectionError("National summary province identity is invalid") from error
        if department_id in department_ids:
            raise CollectionError("National summary contains duplicate provinces")
        department_ids.add(department_id)
        if not item.get("departmentName") or not isinstance(item.get("totalScore"), Real):
            raise CollectionError("National summary province score is invalid")
        group_scores = item.get("groupScores")
        if not isinstance(group_scores, dict) or set(group_scores) != GROUP_CODES:
            raise CollectionError("National summary group scores are incomplete")
        if not all(isinstance(value, Real) for value in group_scores.values()):
            raise CollectionError("National summary group score is invalid")
