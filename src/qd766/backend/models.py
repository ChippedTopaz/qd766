from __future__ import annotations

import uuid
from datetime import datetime, date
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    Date,
    ForeignKey,
    Index,
    Integer,
    JSON,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

JsonDocument = JSON().with_variant(JSONB(), "postgresql")
RecordId = BigInteger().with_variant(Integer(), "sqlite")


class Base(DeclarativeBase):
    pass


class Department(Base):
    __tablename__ = "departments"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    code: Mapped[str | None] = mapped_column(String(64), index=True)
    name: Mapped[str | None] = mapped_column(Text)
    department_type: Mapped[str | None] = mapped_column(String(64))
    department_level: Mapped[str | None] = mapped_column(String(64))
    agency_level: Mapped[str | None] = mapped_column(String(64))
    attributes: Mapped[dict[str, Any]] = mapped_column(JsonDocument, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class Formality(Base):
    __tablename__ = "formalities"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    code: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    name: Mapped[str] = mapped_column(Text)
    state: Mapped[str | None] = mapped_column(String(40))
    owning_department_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("departments.id", ondelete="RESTRICT"), index=True
    )
    attributes: Mapped[dict[str, Any]] = mapped_column(JsonDocument, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class FormalityDepartment(Base):
    __tablename__ = "formality_departments"
    __table_args__ = (
        CheckConstraint(
            "relation_type IN ('applied', 'publishing')",
            name="ck_formality_department_relation",
        ),
        Index("ix_formality_department_department", "department_id", "relation_type"),
    )

    formality_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("formalities.id", ondelete="CASCADE"), primary_key=True
    )
    department_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("departments.id", ondelete="CASCADE"), primary_key=True
    )
    relation_type: Mapped[str] = mapped_column(String(16), primary_key=True)


class Snapshot(Base):
    __tablename__ = "snapshots"
    __table_args__ = (
        CheckConstraint("period_type IN ('month', 'quarter', 'year')", name="ck_snapshot_period"),
        CheckConstraint(
            "(period_type = 'month' AND period_value BETWEEN 1 AND 12) OR "
            "(period_type = 'quarter' AND period_value BETWEEN 1 AND 4) OR "
            "(period_type = 'year' AND period_value IS NULL)",
            name="ck_snapshot_period_value",
        ),
        CheckConstraint("scope IN ('all', 'formality')", name="ck_snapshot_scope"),
        CheckConstraint(
            "(scope = 'all' AND formality_id IS NULL) OR "
            "(scope = 'formality' AND formality_id IS NOT NULL)",
            name="ck_snapshot_formality_scope",
        ),
        CheckConstraint("state IN ('complete', 'incomplete')", name="ck_snapshot_state"),
        Index("ix_snapshot_lookup", "root_department_id", "period_type", "year", "period_value", "scope"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    snapshot_key: Mapped[str] = mapped_column(String(240), unique=True)
    schema_version: Mapped[int] = mapped_column(Integer)
    root_department_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("departments.id", ondelete="RESTRICT"), index=True
    )
    period_type: Mapped[str] = mapped_column(String(16))
    year: Mapped[int] = mapped_column(Integer)
    period_value: Mapped[int | None] = mapped_column(Integer)
    scope: Mapped[str] = mapped_column(String(16))
    formality_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    state: Mapped[str] = mapped_column(String(16))
    province_aggregated_score: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    province_aggregated_maximum: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    policy: Mapped[dict[str, Any]] = mapped_column(JsonDocument, default=dict)
    status_detail: Mapped[dict[str, Any]] = mapped_column(JsonDocument, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )

    root_department: Mapped[Department] = relationship()
    datasets: Mapped[list["Dataset"]] = relationship(
        back_populates="snapshot", cascade="all, delete-orphan", order_by="Dataset.position"
    )


class Dataset(Base):
    __tablename__ = "datasets"
    __table_args__ = (
        UniqueConstraint("snapshot_id", "group_name", name="uq_dataset_snapshot_group"),
        CheckConstraint("schema_kind IN ('metrics', 'parameters')", name="ck_dataset_schema_kind"),
        CheckConstraint("length(raw_sha256) = 64", name="ck_dataset_raw_sha256"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    snapshot_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("snapshots.id", ondelete="CASCADE"), index=True
    )
    position: Mapped[int] = mapped_column(Integer)
    group_name: Mapped[str] = mapped_column(String(80))
    schema_kind: Mapped[str] = mapped_column(String(16))
    formula_status: Mapped[str] = mapped_column(String(80))
    score_policy: Mapped[str] = mapped_column(String(40))
    raw_path: Mapped[str] = mapped_column(Text)
    raw_sha256: Mapped[str] = mapped_column(String(64))
    details: Mapped[dict[str, Any]] = mapped_column(JsonDocument, default=dict)

    snapshot: Mapped[Snapshot] = relationship(back_populates="datasets")
    entities: Mapped[list["Entity"]] = relationship(
        back_populates="dataset", cascade="all, delete-orphan", order_by="Entity.position"
    )


class Entity(Base):
    __tablename__ = "entities"
    __table_args__ = (
        UniqueConstraint("dataset_id", "entity_kind", "department_id", name="uq_entity_dataset_kind_department"),
        CheckConstraint("entity_kind IN ('root', 'child')", name="ck_entity_kind"),
        Index("ix_entity_department", "department_id", "dataset_id"),
    )

    id: Mapped[int] = mapped_column(RecordId, primary_key=True, autoincrement=True)
    dataset_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("datasets.id", ondelete="CASCADE"), index=True
    )
    department_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("departments.id", ondelete="RESTRICT")
    )
    entity_kind: Mapped[str] = mapped_column(String(16))
    position: Mapped[int] = mapped_column(Integer)
    api_score: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    api_max_score: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    api_ratio: Mapped[Decimal | None] = mapped_column(Numeric(12, 6))
    score_source: Mapped[str] = mapped_column(String(40))
    formula_applied: Mapped[bool] = mapped_column(default=False)
    parameters: Mapped[dict[str, Any]] = mapped_column(JsonDocument, default=dict)
    source_metadata: Mapped[dict[str, Any]] = mapped_column(JsonDocument, default=dict)

    dataset: Mapped[Dataset] = relationship(back_populates="entities")
    department: Mapped[Department] = relationship()
    metrics: Mapped[list["Metric"]] = relationship(
        back_populates="entity", cascade="all, delete-orphan", order_by="Metric.position"
    )


class Metric(Base):
    __tablename__ = "metrics"
    __table_args__ = (
        UniqueConstraint("entity_id", "code", name="uq_metric_entity_code"),
        Index("ix_metric_code", "code"),
    )

    id: Mapped[int] = mapped_column(RecordId, primary_key=True, autoincrement=True)
    entity_id: Mapped[int] = mapped_column(
        ForeignKey("entities.id", ondelete="CASCADE"), index=True
    )
    position: Mapped[int] = mapped_column(Integer)
    code: Mapped[str] = mapped_column(String(120))
    name: Mapped[str] = mapped_column(Text)
    numerator: Mapped[Decimal | None] = mapped_column(Numeric(24, 6))
    denominator: Mapped[Decimal | None] = mapped_column(Numeric(24, 6))
    ratio: Mapped[Decimal | None] = mapped_column(Numeric(12, 6))
    api_score: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    api_max_score: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    extras: Mapped[dict[str, Any]] = mapped_column(JsonDocument, default=dict)

    entity: Mapped[Entity] = relationship(back_populates="metrics")


class CollectionJob(Base):
    __tablename__ = "collection_jobs"
    __table_args__ = (
        CheckConstraint(
            "state IN ('queued', 'running', 'succeeded', 'failed', 'halted')",
            name="ck_collection_job_state",
        ),
        Index("ix_collection_job_claim", "state", "priority", "next_run_at", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    idempotency_key: Mapped[str] = mapped_column(String(240), unique=True)
    state: Mapped[str] = mapped_column(String(16), default="queued")
    priority: Mapped[int] = mapped_column(Integer, default=100)
    request: Mapped[dict[str, Any]] = mapped_column(JsonDocument)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    next_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    locked_by: Mapped[str | None] = mapped_column(String(160))
    error: Mapped[dict[str, Any] | None] = mapped_column(JsonDocument)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class UserAccount(Base):
    __tablename__ = "user_accounts"
    __table_args__ = (
        CheckConstraint(
            "plan IN ('free', 'paid', 'admin')", name="ck_user_account_plan"
        ),
        CheckConstraint("credit_balance >= 0", name="ck_user_credit_balance"),
        CheckConstraint("credit_reserved >= 0", name="ck_user_credit_reserved"),
        CheckConstraint("role IN ('user', 'admin')", name="ck_account_role"),
        CheckConstraint("access_tier IN ('province', 'agency', 'national')", name="ck_account_access_tier"),
        CheckConstraint("access_tier != 'agency' OR (unit_department_id IS NOT NULL AND root_department_id IS NOT NULL)", name="ck_account_unit_scope"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    external_subject: Mapped[str] = mapped_column(String(240), unique=True)
    email: Mapped[str | None] = mapped_column(String(320))
    role: Mapped[str] = mapped_column(String(16), default="user", server_default="user")
    trial_admitted: Mapped[bool] = mapped_column(default=False, server_default=text("false"))
    access_tier: Mapped[str] = mapped_column(String(16), default="province", server_default="province")
    unit_department_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("departments.id", ondelete="RESTRICT"))
    root_department_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("departments.id", ondelete="RESTRICT"), index=True
    )
    display_name: Mapped[str] = mapped_column(Text)
    plan: Mapped[str] = mapped_column(String(16), default="free")
    credit_balance: Mapped[int] = mapped_column(Integer, default=0)
    credit_reserved: Mapped[int] = mapped_column(Integer, default=0)
    active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class TriviaQuestion(Base):
    __tablename__ = 'trivia_questions'
    __table_args__ = (CheckConstraint("state IN ('draft','published','retired')", name='ck_trivia_state'),)
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    prompt: Mapped[str] = mapped_column(Text)
    choices: Mapped[list] = mapped_column(JSON)
    correct_index: Mapped[int] = mapped_column(Integer)
    explanation: Mapped[str] = mapped_column(Text, default='')
    state: Mapped[str] = mapped_column(String(16), default='draft')
    locked: Mapped[bool] = mapped_column(default=False)
    revision: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class TriviaProfile(Base):
    __tablename__ = 'trivia_profiles'
    account_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('user_accounts.id', ondelete='CASCADE'), primary_key=True)
    pending_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey('trivia_questions.id', ondelete='SET NULL'))
    pending_deadline: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    round_id: Mapped[uuid.UUID] = mapped_column(Uuid, default=uuid.uuid4)
    score: Mapped[int] = mapped_column(Integer, default=0)
    streak: Mapped[int] = mapped_column(Integer, default=0)
    best: Mapped[int] = mapped_column(Integer, default=0)
    answered: Mapped[int] = mapped_column(Integer, default=0)


class TriviaAnswer(Base):
    __tablename__ = 'trivia_answers'
    __table_args__ = (Index('ix_trivia_answers_question_correct_account','question_id','correct','account_id'),)
    account_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('user_accounts.id', ondelete='CASCADE'), primary_key=True)
    question_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('trivia_questions.id', ondelete='RESTRICT'), primary_key=True)
    round_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    choice: Mapped[int | None] = mapped_column(Integer)
    timed_out: Mapped[bool] = mapped_column(default=False)
    correct: Mapped[bool] = mapped_column()
    score_after: Mapped[int] = mapped_column(Integer)
    streak_after: Mapped[int] = mapped_column(Integer)
    best_after: Mapped[int] = mapped_column(Integer)
    answered_after: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AccountCollectionPermission(Base):
    """Separate capability: province/agency scope and paid plan do not imply collection permission."""
    __tablename__ = "account_collection_permissions"
    account_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("user_accounts.id", ondelete="CASCADE"), primary_key=True)
    enabled: Mapped[bool] = mapped_column(default=False, server_default=text("false"))
    granted_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("user_accounts.id", ondelete="RESTRICT"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class LoginAttempt(Base):
    __tablename__ = "login_attempts"
    state_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    binding_hash: Mapped[str] = mapped_column(String(64))
    nonce: Mapped[str] = mapped_column(String(80))
    verifier: Mapped[str] = mapped_column(String(100))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    invitation_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("trial_invitations.id", ondelete="SET NULL"))
    public_registration: Mapped[bool] = mapped_column(default=False, server_default="false")


class TrialInvitation(Base):
    __tablename__ = "trial_invitations"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("user_accounts.id", ondelete="RESTRICT"))
    recipient_email: Mapped[str | None] = mapped_column(String(320))
    root_department_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("departments.id", ondelete="RESTRICT"))
    access_tier: Mapped[str] = mapped_column(String(16))
    unit_department_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("departments.id", ondelete="RESTRICT"))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    used_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("user_accounts.id", ondelete="RESTRICT"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    __table_args__ = (CheckConstraint("access_tier IN ('province', 'agency', 'national')", name="ck_invite_tier"),
        CheckConstraint("access_tier != 'agency' OR unit_department_id IS NOT NULL", name="ck_invite_unit"))


class SharedTrialLink(Base):
    __tablename__ = "shared_trial_links"
    __table_args__ = (CheckConstraint("max_registrations > 0 AND registered_count >= 0 AND registered_count <= max_registrations", name="ck_shared_link_capacity"),)
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("user_accounts.id", ondelete="RESTRICT"))
    max_registrations: Mapped[int] = mapped_column(Integer)
    registered_count: Mapped[int] = mapped_column(Integer, default=0)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class SharedTrialLogin(Base):
    __tablename__ = "shared_trial_logins"
    state_hash: Mapped[str] = mapped_column(ForeignKey("login_attempts.state_hash", ondelete="CASCADE"), primary_key=True)
    link_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("shared_trial_links.id", ondelete="RESTRICT"))


class TrialRegistration(Base):
    __tablename__ = "trial_registrations"
    __table_args__ = (
        CheckConstraint("state IN ('draft','pending','approved','rejected')", name="ck_registration_state"),
        CheckConstraint("requested_tier IN ('province','agency')", name="ck_registration_tier"),
        CheckConstraint("link_id IS NULL OR requested_tier = 'agency'", name="ck_registration_link_tier"),
        CheckConstraint("state = 'draft' OR (root_department_id IS NOT NULL AND ((requested_tier = 'agency' AND unit_department_id IS NOT NULL) OR (requested_tier = 'province' AND unit_department_id IS NULL)))", name="ck_registration_scope"),)
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    account_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("user_accounts.id", ondelete="RESTRICT"), unique=True)
    link_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("shared_trial_links.id", ondelete="RESTRICT"))
    requested_tier: Mapped[str] = mapped_column(String(16), default="agency", server_default="agency")
    full_name: Mapped[str | None] = mapped_column(String(160))
    birth_date: Mapped[date | None] = mapped_column(Date)
    gender: Mapped[str | None] = mapped_column(String(16))
    workplace: Mapped[str | None] = mapped_column(String(240))
    state: Mapped[str] = mapped_column(String(16), default="draft")
    root_department_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("departments.id", ondelete="RESTRICT"))
    unit_department_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("departments.id", ondelete="RESTRICT"))
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("user_accounts.id", ondelete="RESTRICT"))
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AdminAudit(Base):
    __tablename__ = "admin_audits"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    actor_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("user_accounts.id", ondelete="RESTRICT"))
    action: Mapped[str] = mapped_column(String(80))
    details: Mapped[dict[str, Any]] = mapped_column(JsonDocument, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class LoginSession(Base):
    __tablename__ = "login_sessions"
    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    account_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("user_accounts.id", ondelete="CASCADE"), index=True)
    csrf_token: Mapped[str] = mapped_column(String(80))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class PaidDataRequest(Base):
    __tablename__ = "paid_data_requests"
    __table_args__ = (
        CheckConstraint(
            "state IN ('reserved', 'waiting', 'ready', 'refunded')",
            name="ck_paid_data_request_state",
        ),
        CheckConstraint("credit_cost > 0", name="ck_paid_data_request_credit_cost"),
        Index("ix_paid_request_account_dataset", "account_id", "dataset_key"),
        Index(
            "uq_paid_request_active_entitlement",
            "account_id",
            "dataset_key",
            unique=True,
            postgresql_where=text("state IN ('reserved', 'waiting', 'ready')"),
            sqlite_where=text("state IN ('reserved', 'waiting', 'ready')"),
        ),
        Index("ix_paid_request_job_state", "collection_job_id", "state"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    account_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("user_accounts.id", ondelete="RESTRICT"), index=True
    )
    idempotency_key: Mapped[str] = mapped_column(String(240), unique=True)
    dataset_key: Mapped[str] = mapped_column(String(240), index=True)
    state: Mapped[str] = mapped_column(String(16), default="reserved")
    credit_cost: Mapped[int] = mapped_column(Integer)
    province_code: Mapped[str] = mapped_column(String(2))
    root_department_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("departments.id", ondelete="RESTRICT"), index=True
    )
    formality_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("formalities.id", ondelete="RESTRICT"), index=True
    )
    period_type: Mapped[str] = mapped_column(String(16))
    year: Mapped[int] = mapped_column(Integer)
    period_value: Mapped[int | None] = mapped_column(Integer)
    collection_job_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("collection_jobs.id", ondelete="RESTRICT"), index=True
    )
    snapshot_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("snapshots.id", ondelete="RESTRICT"), index=True
    )
    error: Mapped[dict[str, Any] | None] = mapped_column(JsonDocument)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    notified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class CreditLedgerEntry(Base):
    __tablename__ = "credit_ledger_entries"
    __table_args__ = (
        CheckConstraint(
            "entry_type IN ('topup', 'reserve', 'charge', 'release', 'adjustment')",
            name="ck_credit_ledger_entry_type",
        ),
        CheckConstraint("amount > 0", name="ck_credit_ledger_amount"),
        Index("ix_credit_ledger_account_created", "account_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    event_key: Mapped[str] = mapped_column(String(240), unique=True)
    account_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("user_accounts.id", ondelete="RESTRICT"), index=True
    )
    paid_request_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("paid_data_requests.id", ondelete="RESTRICT"), index=True
    )
    entry_type: Mapped[str] = mapped_column(String(16))
    amount: Mapped[int] = mapped_column(Integer)
    available_delta: Mapped[int] = mapped_column(Integer)
    reserved_delta: Mapped[int] = mapped_column(Integer)
    available_after: Mapped[int] = mapped_column(Integer)
    reserved_after: Mapped[int] = mapped_column(Integer)
    details: Mapped[dict[str, Any]] = mapped_column(JsonDocument, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class CreditLot(Base):
    """Independent source-aware wallet; not activated for existing account balances."""
    __tablename__ = "credit_lots"
    __table_args__ = (
        CheckConstraint("source IN ('subscription', 'purchased')", name="ck_credit_lot_source"),
        CheckConstraint("available >= 0 AND reserved >= 0", name="ck_credit_lot_balance"),
        CheckConstraint("(source = 'purchased' AND expires_at IS NULL) OR (source = 'subscription' AND expires_at IS NOT NULL)",
                        name="ck_credit_lot_expiration"),
        Index("ix_credit_lot_account", "account_id"),
    )
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    account_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("user_accounts.id", ondelete="RESTRICT"))
    source: Mapped[str] = mapped_column(String(16))
    available: Mapped[int] = mapped_column(Integer)
    reserved: Mapped[int] = mapped_column(Integer, default=0)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class CreditHold(Base):
    __tablename__ = "credit_holds"
    __table_args__ = (
        UniqueConstraint("account_id", "request_key", name="uq_credit_hold_request"),
        CheckConstraint("state IN ('reserved', 'charged', 'refunded')", name="ck_credit_hold_state"),
        CheckConstraint("amount > 0", name="ck_credit_hold_amount"),
    )
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    account_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("user_accounts.id", ondelete="RESTRICT"))
    request_key: Mapped[str] = mapped_column(String(240))
    state: Mapped[str] = mapped_column(String(16), default="reserved")
    amount: Mapped[int] = mapped_column(Integer)
    allocations: Mapped[list] = mapped_column(JsonDocument)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class CreditWalletEvent(Base):
    __tablename__ = "credit_wallet_events"
    __table_args__ = (
        UniqueConstraint("account_id", "event_key", name="uq_credit_wallet_event"),
        CheckConstraint("kind IN ('grant', 'reserve', 'charge', 'refund', 'expire')", name="ck_credit_wallet_event_kind"),
        CheckConstraint("amount > 0", name="ck_credit_wallet_event_amount"),
        Index("ix_credit_wallet_event_account", "account_id", "created_at"),
    )
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    account_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("user_accounts.id", ondelete="RESTRICT"))
    event_key: Mapped[str] = mapped_column(String(250))
    kind: Mapped[str] = mapped_column(String(16))
    amount: Mapped[int] = mapped_column(Integer)
    details: Mapped[dict] = mapped_column(JsonDocument)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class CreditWalletEnrollment(Base):
    """Explicit opt-in; existing legacy Credit are never classified as purchased."""
    __tablename__ = "credit_wallet_enrollments"
    account_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("user_accounts.id", ondelete="RESTRICT"), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class SubscriptionCycle(Base):
    """Explicit monthly boundaries; isolated until commercial activation is approved."""
    __tablename__ = "subscription_cycles"
    __table_args__ = (
        UniqueConstraint("account_id", "operation_key", name="uq_subscription_cycle_operation"),
        CheckConstraint("tier IN ('agency', 'province')", name="ck_subscription_cycle_tier"),
        CheckConstraint("origin IN ('trial', 'paid', 'redemption')", name="ck_subscription_cycle_origin"),
        CheckConstraint("ends_at > starts_at", name="ck_subscription_cycle_dates"),
        CheckConstraint("included_credit >= 0", name="ck_subscription_cycle_credit"),
        Index("ix_subscription_cycle_account", "account_id", "starts_at"),
    )
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    account_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("user_accounts.id", ondelete="RESTRICT"))
    operation_key: Mapped[str] = mapped_column(String(200))
    tier: Mapped[str] = mapped_column(String(16))
    origin: Mapped[str] = mapped_column(String(16))
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    included_credit: Mapped[int] = mapped_column(Integer)
    granted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class UserNotification(Base):
    __tablename__ = "user_notifications"
    __table_args__ = (
        CheckConstraint(
            "kind IN ('data-ready', 'data-failed')",
            name="ck_user_notification_kind",
        ),
        UniqueConstraint("paid_request_id", "kind", name="uq_notification_request_kind"),
        Index("ix_notification_account_read", "account_id", "read_at", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    account_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("user_accounts.id", ondelete="CASCADE"), index=True
    )
    paid_request_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("paid_data_requests.id", ondelete="CASCADE"), index=True
    )
    kind: Mapped[str] = mapped_column(String(24))
    title: Mapped[str] = mapped_column(Text)
    message: Mapped[str] = mapped_column(Text)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class NationalSummarySnapshot(Base):
    __tablename__ = "national_summary_snapshots"
    __table_args__ = (
        CheckConstraint(
            "period_type IN ('month', 'quarter', 'year')",
            name="ck_national_summary_period",
        ),
        CheckConstraint(
            "(period_type = 'month' AND period_value BETWEEN 1 AND 12) OR "
            "(period_type = 'quarter' AND period_value BETWEEN 1 AND 4) OR "
            "(period_type = 'year' AND period_value IS NULL)",
            name="ck_national_summary_period_value",
        ),
        CheckConstraint(
            "completeness_state = 'complete'",
            name="ck_national_summary_completeness_state",
        ),
        CheckConstraint(
            "group_count = 6",
            name="ck_national_summary_group_count",
        ),
        Index(
            "ix_national_summary_lookup",
            "period_type",
            "year",
            "period_value",
            "captured_at",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    summary_key: Mapped[str] = mapped_column(String(240), unique=True)
    period_type: Mapped[str] = mapped_column(String(16))
    year: Mapped[int] = mapped_column(Integer)
    period_value: Mapped[int | None] = mapped_column(Integer)
    department_type: Mapped[str] = mapped_column(String(40), default="ADMINISTRATIVE_UNIT")
    province_count: Mapped[int] = mapped_column(Integer)
    completeness_state: Mapped[str] = mapped_column(String(16), default="complete")
    group_count: Mapped[int] = mapped_column(Integer, default=6)
    group_codes: Mapped[list[str]] = mapped_column(JsonDocument)
    raw_sha256: Mapped[str] = mapped_column(String(64))
    request_payload: Mapped[dict[str, Any]] = mapped_column(JsonDocument)
    response_data: Mapped[dict[str, Any]] = mapped_column(JsonDocument)
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class DailyObservation(Base):
    """Immutable linkage of a reporting day to real, complete source captures."""
    __tablename__ = "daily_observations"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    block_key: Mapped[str] = mapped_column(String(160), unique=True)
    report_date: Mapped[date] = mapped_column(Date, index=True)
    root_department_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("departments.id", ondelete="RESTRICT"), index=True)
    period_type: Mapped[str] = mapped_column(String(16))
    year: Mapped[int] = mapped_column(Integer)
    period_value: Mapped[int | None] = mapped_column(Integer)
    snapshot_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("snapshots.id", ondelete="RESTRICT"))
    national_summary_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("national_summary_snapshots.id", ondelete="RESTRICT"))
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    snapshot: Mapped[Snapshot] = relationship()
    national_summary: Mapped[NationalSummarySnapshot] = relationship()
    __table_args__ = (Index("ix_daily_lookup", "root_department_id", "period_type", "year", "period_value", "report_date"),)


class CollectionBatch(Base):
    __tablename__ = "collection_batches"
    __table_args__ = (
        CheckConstraint(
            "state IN ('queued', 'running', 'succeeded', 'failed', 'halted')",
            name="ck_collection_batch_state",
        ),
        Index("ix_collection_batch_state_created", "state", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    idempotency_key: Mapped[str] = mapped_column(String(240), unique=True)
    state: Mapped[str] = mapped_column(String(16), default="queued")
    province_code: Mapped[str] = mapped_column(String(2))
    root_department_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("departments.id", ondelete="RESTRICT"), index=True
    )
    period_type: Mapped[str] = mapped_column(String(16))
    year: Mapped[int] = mapped_column(Integer)
    period_value: Mapped[int | None] = mapped_column(Integer)
    filters: Mapped[dict[str, Any]] = mapped_column(JsonDocument, default=dict)
    catalog_version: Mapped[str] = mapped_column(String(160))
    total_items: Mapped[int] = mapped_column(Integer)
    available_items: Mapped[int] = mapped_column(Integer, default=0)
    completed_items: Mapped[int] = mapped_column(Integer, default=0)
    failed_items: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[dict[str, Any] | None] = mapped_column(JsonDocument)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class CollectionBatchItem(Base):
    __tablename__ = "collection_batch_items"
    __table_args__ = (
        CheckConstraint(
            "state IN ('pending', 'queued', 'running', 'succeeded', 'failed', 'halted', 'skipped')",
            name="ck_collection_batch_item_state",
        ),
        UniqueConstraint("batch_id", "formality_id", name="uq_batch_item_formality"),
        Index("ix_batch_item_next", "batch_id", "state", "position"),
    )

    id: Mapped[int] = mapped_column(RecordId, primary_key=True, autoincrement=True)
    batch_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("collection_batches.id", ondelete="CASCADE"), index=True
    )
    position: Mapped[int] = mapped_column(Integer)
    formality_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    formality_code: Mapped[str] = mapped_column(String(80))
    formality_name: Mapped[str] = mapped_column(Text)
    state: Mapped[str] = mapped_column(String(16), default="pending")
    job_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("collection_jobs.id", ondelete="SET NULL"), index=True
    )
    error: Mapped[dict[str, Any] | None] = mapped_column(JsonDocument)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class ProvinceCollectionBatch(Base):
    __tablename__ = "province_collection_batches"
    __table_args__ = (
        CheckConstraint(
            "state IN ('queued', 'running', 'succeeded', 'failed', 'halted')",
            name="ck_province_collection_batch_state",
        ),
        CheckConstraint(
            "period_type IN ('month', 'quarter', 'year')",
            name="ck_province_collection_batch_period",
        ),
        CheckConstraint(
            "(period_type = 'month' AND period_value BETWEEN 1 AND 12) OR "
            "(period_type = 'quarter' AND period_value BETWEEN 1 AND 4) OR "
            "(period_type = 'year' AND period_value IS NULL)",
            name="ck_province_collection_batch_period_value",
        ),
        Index("ix_province_collection_batch_state_created", "state", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    idempotency_key: Mapped[str] = mapped_column(String(240), unique=True)
    state: Mapped[str] = mapped_column(String(16), default="queued")
    period_type: Mapped[str] = mapped_column(String(16))
    year: Mapped[int] = mapped_column(Integer)
    period_value: Mapped[int | None] = mapped_column(Integer)
    catalog_version: Mapped[str] = mapped_column(String(160))
    total_items: Mapped[int] = mapped_column(Integer)
    available_items: Mapped[int] = mapped_column(Integer, default=0)
    completed_items: Mapped[int] = mapped_column(Integer, default=0)
    failed_items: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[dict[str, Any] | None] = mapped_column(JsonDocument)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class ProvinceCollectionBatchItem(Base):
    __tablename__ = "province_collection_batch_items"
    __table_args__ = (
        CheckConstraint(
            "state IN ('pending', 'queued', 'running', 'succeeded', 'failed', 'halted', 'skipped')",
            name="ck_province_collection_batch_item_state",
        ),
        UniqueConstraint(
            "batch_id", "root_department_id", name="uq_province_batch_item_root"
        ),
        Index("ix_province_batch_item_next", "batch_id", "state", "position"),
    )

    id: Mapped[int] = mapped_column(RecordId, primary_key=True, autoincrement=True)
    batch_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("province_collection_batches.id", ondelete="CASCADE"), index=True
    )
    position: Mapped[int] = mapped_column(Integer)
    province_code: Mapped[str] = mapped_column(String(2))
    province_name: Mapped[str] = mapped_column(Text)
    root_department_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("departments.id", ondelete="RESTRICT"), index=True
    )
    state: Mapped[str] = mapped_column(String(16), default="pending")
    job_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("collection_jobs.id", ondelete="SET NULL"), index=True
    )
    error: Mapped[dict[str, Any] | None] = mapped_column(JsonDocument)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class GeminiAnalysis(Base):
    __tablename__ = "gemini_analyses"
    __table_args__ = (
        UniqueConstraint("account_id", "request_token", name="uq_gemini_analysis_token"),
        CheckConstraint("state IN ('queued', 'running', 'ready', 'failed', 'cancelled')", name="ck_gemini_analysis_state"),
        Index("ix_gemini_analysis_owner", "account_id", "created_at"),
        Index("ix_gemini_analysis_queue", "state", "created_at", "id"),
    )
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    account_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("user_accounts.id", ondelete="RESTRICT"))
    request_token: Mapped[uuid.UUID] = mapped_column(Uuid)
    context: Mapped[dict[str, Any]] = mapped_column(JsonDocument)
    evidence: Mapped[dict[str, Any]] = mapped_column(JsonDocument)
    result: Mapped[dict[str, Any] | None] = mapped_column(JsonDocument)
    state: Mapped[str] = mapped_column(String(16), default="running")
    model: Mapped[str] = mapped_column(String(120))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class FormulaConfigRevision(Base):
    __tablename__ = 'formula_config_revisions'
    version: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    content: Mapped[dict] = mapped_column(JSON)
    note: Mapped[str] = mapped_column(String(500))
    actor_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey('user_accounts.id', ondelete='RESTRICT'), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class FormulaConfigHead(Base):
    __tablename__ = 'formula_config_head'
    __table_args__ = (CheckConstraint('id = 1', name='ck_formula_config_singleton'),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    version: Mapped[int] = mapped_column(ForeignKey('formula_config_revisions.version', ondelete='RESTRICT'))


class AnalysisConfigRevision(Base):
    __tablename__ = 'analysis_config_revisions'
    __table_args__ = (CheckConstraint('version > 0',name='ck_analysis_config_version'),)
    version: Mapped[int] = mapped_column(Integer,primary_key=True,autoincrement=False)
    guidance: Mapped[str] = mapped_column(Text)
    knowledge: Mapped[str] = mapped_column(Text)
    note: Mapped[str] = mapped_column(String(500))
    actor_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('user_accounts.id',ondelete='RESTRICT'))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class AnalysisConfigHead(Base):
    __tablename__ = 'analysis_config_head'
    __table_args__ = (CheckConstraint('id = 1',name='ck_analysis_config_singleton'),)
    id: Mapped[int] = mapped_column(Integer,primary_key=True,autoincrement=False)
    version: Mapped[int] = mapped_column(ForeignKey('analysis_config_revisions.version',ondelete='RESTRICT'))


class AnalysisGroupConfigRevision(Base):
    __tablename__ = 'analysis_group_config_revisions'
    version: Mapped[int] = mapped_column(ForeignKey('analysis_config_revisions.version',ondelete='RESTRICT'),primary_key=True)
    group_id: Mapped[str] = mapped_column(String(64),primary_key=True)
    guidance: Mapped[str] = mapped_column(Text)
    knowledge: Mapped[str] = mapped_column(Text)


class AnalysisFeatureControl(Base):
    __tablename__ = 'analysis_feature_control'
    __table_args__ = (CheckConstraint('id = 1 AND revision > 0',name='ck_analysis_feature_singleton'),)
    id: Mapped[int] = mapped_column(Integer,primary_key=True,autoincrement=False)
    enabled: Mapped[bool] = mapped_column(default=True)
    revision: Mapped[int] = mapped_column(Integer)
    actor_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('user_accounts.id',ondelete='RESTRICT'))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class AnalysisQueueEntry(Base):
    __tablename__ = "analysis_queue_entries"
    analysis_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("gemini_analyses.id", ondelete="RESTRICT"), primary_key=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    worker_token: Mapped[uuid.UUID | None] = mapped_column(Uuid)


class CollectionControl(Base):
    __tablename__ = "collection_controls"
    __table_args__ = (
        CheckConstraint(
            "circuit_state IN ('closed', 'open')",
            name="ck_collection_control_circuit_state",
        ),
    )

    key: Mapped[str] = mapped_column(String(80), primary_key=True)
    circuit_state: Mapped[str] = mapped_column(String(16), default="closed")
    reason: Mapped[str | None] = mapped_column(String(160))
    detail: Mapped[dict[str, Any] | None] = mapped_column(JsonDocument)
    opened_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    lease_locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    lease_locked_by: Mapped[str | None] = mapped_column(String(160))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
