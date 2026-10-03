from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from qd766.periods import PeriodSelection

from .jobs import enqueue_job, request_idempotency_key
from .models import (
    CollectionControl,
    CollectionJob,
    CreditLedgerEntry,
    PaidDataRequest,
    Snapshot,
    UserAccount,
    UserNotification,
)


class PaidRequestError(RuntimeError):
    pass


class PaidPlanRequired(PaidRequestError):
    pass


class InsufficientCredits(PaidRequestError):
    pass


class CollectionUnavailable(PaidRequestError):
    pass


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def top_up_credits(
    session: Session,
    account_id: uuid.UUID,
    amount: int,
    *,
    event_key: str,
    details: dict[str, Any] | None = None,
) -> CreditLedgerEntry:
    if amount <= 0:
        raise ValueError("Credit top-up amount must be positive")
    account = _locked_account(session, account_id)
    existing = session.scalar(
        select(CreditLedgerEntry).where(CreditLedgerEntry.event_key == event_key)
    )
    if existing is not None:
        return existing
    account.credit_balance += amount
    return _ledger_entry(
        session,
        account,
        event_key=event_key,
        entry_type="topup",
        amount=amount,
        available_delta=amount,
        reserved_delta=0,
        details=details or {},
    )


def create_paid_data_request(
    session: Session,
    *,
    account_id: uuid.UUID,
    province_code: str,
    root_department_id: uuid.UUID,
    formality_id: uuid.UUID,
    period_type: str,
    year: int,
    period_value: int | None,
    credit_cost: int,
    idempotency_token: str,
    allow_trial: bool = False,
) -> tuple[PaidDataRequest, bool]:
    if credit_cost <= 0:
        raise ValueError("Credit cost must be positive")
    PeriodSelection(period_type, year, period_value).validate_collectable()
    if len(province_code) != 2 or not province_code.isdigit():
        raise ValueError("Province code must contain two digits")
    account = _locked_account(session, account_id)
    if not account.active or (account.plan not in {"paid", "admin"} and not allow_trial):
        raise PaidPlanRequired("A paid account is required")

    idempotency_key = _paid_idempotency_key(account.id, idempotency_token)
    existing = session.scalar(
        select(PaidDataRequest).where(
            PaidDataRequest.idempotency_key == idempotency_key
        )
    )
    if existing is not None:
        return existing, False

    request_value = _collection_request(
        root_department_id=root_department_id,
        formality_id=formality_id,
        period_type=period_type,
        year=year,
        period_value=period_value,
    )
    dataset_key = request_idempotency_key(request_value)
    entitlement = session.scalar(
        select(PaidDataRequest)
        .where(
            PaidDataRequest.account_id == account.id,
            PaidDataRequest.dataset_key == dataset_key,
            PaidDataRequest.state.in_(("reserved", "waiting", "ready")),
        )
        .order_by(PaidDataRequest.created_at.desc())
        .limit(1)
    )
    if entitlement is not None:
        return entitlement, False
    if account.credit_balance < credit_cost:
        raise InsufficientCredits("Credit balance is insufficient")

    snapshot = _matching_snapshot(
        session,
        root_department_id=root_department_id,
        formality_id=formality_id,
        period_type=period_type,
        year=year,
        period_value=period_value,
    )
    control = session.get(CollectionControl, "dvcqg")
    if snapshot is None and control is not None and control.circuit_state == "open":
        raise CollectionUnavailable("DVCQG collection circuit is open")

    paid_request = PaidDataRequest(
        account_id=account.id,
        idempotency_key=idempotency_key,
        dataset_key=dataset_key,
        state="reserved",
        credit_cost=credit_cost,
        province_code=province_code,
        root_department_id=root_department_id,
        formality_id=formality_id,
        period_type=period_type,
        year=year,
        period_value=period_value,
    )
    session.add(paid_request)
    session.flush()
    account.credit_balance -= credit_cost
    account.credit_reserved += credit_cost
    _ledger_entry(
        session,
        account,
        paid_request=paid_request,
        event_key=f"paid-request:{paid_request.id}:reserve",
        entry_type="reserve",
        amount=credit_cost,
        available_delta=-credit_cost,
        reserved_delta=credit_cost,
        details={"datasetKey": dataset_key},
    )

    if snapshot is not None:
        _settle_request(session, paid_request, account, snapshot)
        return paid_request, True

    job, _ = enqueue_job(session, request_value, priority=50)
    paid_request.collection_job_id = job.id
    if job.state in {"queued", "running"}:
        paid_request.state = "waiting"
    else:
        _refund_request(
            session,
            paid_request,
            account,
            {"kind": "job-not-runnable", "jobState": job.state},
        )
    session.flush()
    return paid_request, True


def settle_paid_requests_for_job(
    session: Session, collection_job: CollectionJob, snapshot: Snapshot
) -> int:
    requests = list(
        session.scalars(
            select(PaidDataRequest)
            .where(
                PaidDataRequest.collection_job_id == collection_job.id,
                PaidDataRequest.state.in_(("reserved", "waiting")),
            )
            .with_for_update()
        )
    )
    for paid_request in requests:
        account = _locked_account(session, paid_request.account_id)
        _settle_request(session, paid_request, account, snapshot)
    return len(requests)


def refund_paid_requests_for_job(
    session: Session, collection_job: CollectionJob, error: dict[str, Any]
) -> int:
    requests = list(
        session.scalars(
            select(PaidDataRequest)
            .where(
                PaidDataRequest.collection_job_id == collection_job.id,
                PaidDataRequest.state.in_(("reserved", "waiting")),
            )
            .with_for_update()
        )
    )
    for paid_request in requests:
        account = _locked_account(session, paid_request.account_id)
        _refund_request(session, paid_request, account, error)
    return len(requests)


def refund_blocked_paid_requests(session: Session) -> int:
    """Release holds when the circuit blocks queued requests; never alter jobs/circuit."""
    control=session.get(CollectionControl,"dvcqg")
    if control is None or control.circuit_state != "open":
        return 0
    pending=list(session.scalars(select(PaidDataRequest).where(
        PaidDataRequest.state.in_(("reserved","waiting"))).order_by(PaidDataRequest.account_id,PaidDataRequest.id).with_for_update(skip_locked=True)))
    for paid in pending:
        account=_locked_account(session,paid.account_id)
        session.refresh(paid)
        if paid.state in {"reserved","waiting"}:
            _refund_request(session,paid,account,{"kind":"circuit-blocked"})
    return len(pending)


def _settle_request(
    session: Session,
    paid_request: PaidDataRequest,
    account: UserAccount,
    snapshot: Snapshot,
) -> None:
    if paid_request.state == "ready":
        return
    account.credit_reserved -= paid_request.credit_cost
    paid_request.state = "ready"
    paid_request.snapshot_id = snapshot.id
    paid_request.error = None
    paid_request.completed_at = utc_now()
    _ledger_entry(
        session,
        account,
        paid_request=paid_request,
        event_key=f"paid-request:{paid_request.id}:charge",
        entry_type="charge",
        amount=paid_request.credit_cost,
        available_delta=0,
        reserved_delta=-paid_request.credit_cost,
        details={"snapshotId": str(snapshot.id)},
    )
    _notification(
        session,
        paid_request,
        kind="data-ready",
        title="Dữ liệu TTHC đã sẵn sàng",
        message="Yêu cầu khai thác dữ liệu theo thủ tục hành chính đã hoàn tất.",
    )


def _refund_request(
    session: Session,
    paid_request: PaidDataRequest,
    account: UserAccount,
    error: dict[str, Any],
) -> None:
    if paid_request.state == "refunded":
        return
    account.credit_balance += paid_request.credit_cost
    account.credit_reserved -= paid_request.credit_cost
    paid_request.state = "refunded"
    paid_request.error = error
    paid_request.completed_at = utc_now()
    _ledger_entry(
        session,
        account,
        paid_request=paid_request,
        event_key=f"paid-request:{paid_request.id}:release",
        entry_type="release",
        amount=paid_request.credit_cost,
        available_delta=paid_request.credit_cost,
        reserved_delta=-paid_request.credit_cost,
        details={"error": error},
    )
    _notification(
        session,
        paid_request,
        kind="data-failed",
        title="Yêu cầu dữ liệu chưa hoàn tất",
        message="Yêu cầu không thành công và toàn bộ credit đã được hoàn trả.",
    )


def _matching_snapshot(
    session: Session,
    *,
    root_department_id: uuid.UUID,
    formality_id: uuid.UUID,
    period_type: str,
    year: int,
    period_value: int | None,
) -> Snapshot | None:
    statement = select(Snapshot).where(
        Snapshot.state == "complete",
        Snapshot.root_department_id == root_department_id,
        Snapshot.scope == "formality",
        Snapshot.formality_id == formality_id,
        Snapshot.period_type == period_type,
        Snapshot.year == year,
    )
    statement = (
        statement.where(Snapshot.period_value.is_(None))
        if period_value is None
        else statement.where(Snapshot.period_value == period_value)
    )
    return session.scalar(statement.order_by(Snapshot.created_at.desc()).limit(1))


def _collection_request(
    *,
    root_department_id: uuid.UUID,
    formality_id: uuid.UUID,
    period_type: str,
    year: int,
    period_value: int | None,
) -> dict[str, Any]:
    period: dict[str, Any] = {"type": period_type, "year": year}
    if period_type in {"month", "quarter"}:
        period[period_type] = period_value
    return {
        "kind": "evaluation-snapshot",
        "rootDepartmentId": str(root_department_id),
        "period": period,
        "scope": "formality",
        "formalityId": str(formality_id),
    }


def _paid_idempotency_key(account_id: uuid.UUID, token: str) -> str:
    if not token.strip():
        raise ValueError("Idempotency token is required")
    digest = hashlib.sha256(f"{account_id}:{token}".encode()).hexdigest()
    return f"paid-request:v1:{digest}"


def _locked_account(session: Session, account_id: uuid.UUID) -> UserAccount:
    account = session.scalar(
        select(UserAccount)
        .where(UserAccount.id == account_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if account is None:
        raise PaidRequestError("Account not found")
    return account


def _ledger_entry(
    session: Session,
    account: UserAccount,
    *,
    event_key: str,
    entry_type: str,
    amount: int,
    available_delta: int,
    reserved_delta: int,
    paid_request: PaidDataRequest | None = None,
    details: dict[str, Any] | None = None,
) -> CreditLedgerEntry:
    entry = CreditLedgerEntry(
        event_key=event_key,
        account_id=account.id,
        paid_request_id=paid_request.id if paid_request else None,
        entry_type=entry_type,
        amount=amount,
        available_delta=available_delta,
        reserved_delta=reserved_delta,
        available_after=account.credit_balance,
        reserved_after=account.credit_reserved,
        details=details or {},
    )
    session.add(entry)
    session.flush()
    return entry


def _notification(
    session: Session,
    paid_request: PaidDataRequest,
    *,
    kind: str,
    title: str,
    message: str,
) -> UserNotification:
    notification = UserNotification(
        account_id=paid_request.account_id,
        paid_request_id=paid_request.id,
        kind=kind,
        title=title,
        message=message,
    )
    session.add(notification)
    paid_request.notified_at = utc_now()
    session.flush()
    return notification
