"""Fixture builder for a separate local schema, never a production API.

Only the owner identity is copied; balances, sessions and original entitlements
are not copied or changed. Reopening the rehearsal never resets its wallet.
"""
import uuid
from datetime import timedelta
from sqlalchemy import select

from .credit_wallet import expire, finish, grant, reserve, utc
from .importer import store_normalized_snapshot
from .jobs import request_idempotency_key
from .local_credit_trial import ROOT, identifier, mock_catalog, mock_snapshot
from .models import AccountCollectionPermission, Formality, PaidDataRequest, UserAccount
from .paid_requests import _collection_request
from .subscriptions import grant_due_cycles, monthly_boundary, schedule_plan
from .wallet_access import enroll


def seed_expiry_rehearsal(db, *, owner, tier, now):
    if not db.info.get("source_wallet_enabled") or tier not in {"agency", "province"}:
        raise ValueError("Explicit source-wallet rehearsal required")
    if owner["email"] != "vietnt89@gmail.com" or not owner["subject"].startswith("google:"):
        raise ValueError("Only the verified local owner identity can rehearse")
    # The launcher selects a dedicated schema. Refuse any other identity here.
    existing = list(db.scalars(select(UserAccount)))
    if existing:
        if (len(existing) != 1 or existing[0].external_subject != owner["subject"]
                or existing[0].access_tier != tier):
            raise ValueError("Rehearsal schema contains unexpected identities")
        return False
    now = utc(now)
    past = now - timedelta(days=65)
    end = monthly_boundary(past, 1)
    store_normalized_snapshot(db, mock_snapshot())
    for item in mock_catalog().select():
        db.add(Formality(id=uuid.UUID(item.id), code=item.code, name=item.name,
                        attributes={"simulation": True}))
    db.flush()
    account = UserAccount(id=uuid.uuid4(), external_subject=owner["subject"],
        email=owner["email"], display_name="Nghiệm thu hết hạn — dữ liệu mô phỏng",
        role="user", active=True, trial_admitted=True, access_tier=tier,
        root_department_id=ROOT,
        unit_department_id=identifier("department:commune") if tier == "agency" else None)
    db.add(account)
    db.flush()
    db.add(AccountCollectionPermission(account_id=account.id, enabled=True))
    enroll(db, account.id, now=past)
    schedule_plan(db, account.id, tier=tier, origin="trial", operation_key="expiry-fixture",
                  starts_at=past, months=1, now=past)
    grant_due_cycles(db, account.id, now=past)
    grant(db, account.id, 600, source="purchased", operation_key="mock-purchased",
          now=past)
    formality = identifier("formality:1")
    selection = _collection_request(root_department_id=ROOT, formality_id=formality,
        period_type="year", year=now.year, period_value=None)
    snapshot = store_normalized_snapshot(db, mock_snapshot(selection))
    paid = PaidDataRequest(account_id=account.id, idempotency_key="wallet:expiry-fixture",
        dataset_key=request_idempotency_key(selection), state="ready", credit_cost=5,
        province_code="25", root_department_id=ROOT, formality_id=formality,
        period_type="year", year=now.year, snapshot_id=snapshot.id,
        created_at=past, completed_at=past, notified_at=past)
    db.add(paid)
    db.flush()
    reserve(db, account.id, 5, request_key=str(paid.id), now=past)
    finish(db, account.id, request_key=str(paid.id), outcome="charge", now=past)
    expire(db, account.id, now=end)
    return True
