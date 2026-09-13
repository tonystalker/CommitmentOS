"""
CommitmentOS — canonical data models (SQLAlchemy).

Every source (Slack, Gmail) resolves into one Commitment object.
The state machine, transition history, and action history are append-only.
"""
import enum
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


# ─────────────────────────────────────────────────────────────────────────────
# Enums
# ─────────────────────────────────────────────────────────────────────────────

class CommitmentState(str, enum.Enum):
    PROPOSED = "PROPOSED"
    CONFIRMED = "CONFIRMED"
    AT_RISK = "AT_RISK"
    BLOCKED = "BLOCKED"
    OVERDUE = "OVERDUE"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class EvidenceSource(str, enum.Enum):
    SLACK = "SLACK"
    GMAIL = "GMAIL"
    LINEAR = "LINEAR"
    MANUAL = "MANUAL"


class ActionType(str, enum.Enum):
    CREATE_LINEAR_TASK = "CREATE_LINEAR_TASK"
    UPDATE_LINEAR_STATUS = "UPDATE_LINEAR_STATUS"
    POST_SLACK_MESSAGE = "POST_SLACK_MESSAGE"
    CREATE_REMINDER = "CREATE_REMINDER"
    ASSIGN_TASK = "ASSIGN_TASK"
    SEND_EXTERNAL_EMAIL = "SEND_EXTERNAL_EMAIL"
    RESCHEDULE_MEETING = "RESCHEDULE_MEETING"
    FINANCIAL_ACTION = "FINANCIAL_ACTION"


class ActionStatus(str, enum.Enum):
    PENDING = "PENDING"
    AUTHORIZED = "AUTHORIZED"
    AWAITING_APPROVAL = "AWAITING_APPROVAL"
    BLOCKED = "BLOCKED"
    EXECUTING = "EXECUTING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    VERIFIED = "VERIFIED"


class RiskLevel(str, enum.Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


# ─────────────────────────────────────────────────────────────────────────────
# Person — canonical identity model
# ─────────────────────────────────────────────────────────────────────────────

class Person(Base):
    __tablename__ = "persons"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid.uuid4()))
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True)
    slack_user_id: Mapped[str | None] = mapped_column(String(100), unique=True, nullable=True)
    linear_username: Mapped[str | None] = mapped_column(String(100), unique=True, nullable=True)
    timezone: Mapped[str] = mapped_column(String(100), default="UTC")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    commitments: Mapped[list["Commitment"]] = relationship("Commitment", back_populates="person")

    def __repr__(self) -> str:
        return f"<Person id={self.id} name={self.display_name!r}>"


# ─────────────────────────────────────────────────────────────────────────────
# Commitment — core domain object
# ─────────────────────────────────────────────────────────────────────────────

class Commitment(Base):
    __tablename__ = "commitments"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid.uuid4()))
    person_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("persons.id"), nullable=False)

    # Core content
    commitment_text: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_action: Mapped[str] = mapped_column(Text, nullable=False)

    # Deadline
    raw_deadline: Mapped[str | None] = mapped_column(String(500), nullable=True)   # "tomorrow", "end of week"
    resolved_deadline: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    source_timestamp: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    timezone: Mapped[str] = mapped_column(String(100), default="UTC")

    # State machine
    state: Mapped[CommitmentState] = mapped_column(
        Enum(CommitmentState, name="commitment_state"),
        default=CommitmentState.PROPOSED,
        nullable=False,
    )

    # Risk
    risk_score: Mapped[float] = mapped_column(Float, default=0.0)
    risk_level: Mapped[RiskLevel] = mapped_column(
        Enum(RiskLevel, name="risk_level"),
        default=RiskLevel.LOW,
    )

    # Multi-dimensional confidence scores (stored as JSON)
    confidence: Mapped[dict[str, float]] = mapped_column(
        JSON,
        default=lambda: {
            "extraction": 0.0,
            "identity": 0.0,
            "date_resolution": 0.0,
            "deduplication": 0.0,
            "action_selection": 0.0,
        },
    )

    # Related external objects
    related_task_ids: Mapped[list[str]] = mapped_column(JSON, default=list)
    related_message_ids: Mapped[list[str]] = mapped_column(JSON, default=list)

    # Supermemory document ID (for semantic memory)
    supermemory_doc_id: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Append-only histories (stored as JSON arrays)
    transition_history: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    action_history: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)

    # Relationships
    person: Mapped["Person"] = relationship("Person", back_populates="commitments")
    evidence: Mapped[list["Evidence"]] = relationship("Evidence", back_populates="commitment", cascade="all, delete-orphan")
    actions: Mapped[list["ActionRecord"]] = relationship("ActionRecord", back_populates="commitment", cascade="all, delete-orphan")
    trace_steps: Mapped[list["TraceStep"]] = relationship("TraceStep", back_populates="commitment", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Commitment id={self.id} state={self.state} person={self.person_id}>"


# ─────────────────────────────────────────────────────────────────────────────
# Evidence — one source of evidence per commitment (Slack msg, email thread, etc.)
# ─────────────────────────────────────────────────────────────────────────────

class Evidence(Base):
    __tablename__ = "evidence"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid.uuid4()))
    commitment_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("commitments.id"), nullable=False)
    source: Mapped[EvidenceSource] = mapped_column(Enum(EvidenceSource, name="evidence_source"), nullable=False)

    # Validated canonical facts extracted from the source — never raw user text stored for re-injection
    extracted_person: Mapped[str | None] = mapped_column(String(255), nullable=True)
    extracted_action: Mapped[str | None] = mapped_column(Text, nullable=True)
    extracted_deadline_phrase: Mapped[str | None] = mapped_column(String(500), nullable=True)
    source_message_id: Mapped[str | None] = mapped_column(String(500), nullable=True)
    source_channel: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source_timestamp: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Confidence of this specific evidence
    extraction_confidence: Mapped[float] = mapped_column(Float, default=0.0)

    # Prompt-injection detection flag (belt-and-suspenders; structural defense is primary)
    injection_flagged: Mapped[bool] = mapped_column(Boolean, default=False)
    injection_flag_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Relationship
    commitment: Mapped["Commitment"] = relationship("Commitment", back_populates="evidence")


# ─────────────────────────────────────────────────────────────────────────────
# ActionRecord — every proposed/executed action (idempotency key, verification)
# ─────────────────────────────────────────────────────────────────────────────

class ActionRecord(Base):
    __tablename__ = "action_records"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid.uuid4()))
    commitment_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("commitments.id"), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(500), unique=True, nullable=False)

    action_type: Mapped[ActionType] = mapped_column(Enum(ActionType, name="action_type"), nullable=False)
    risk_level: Mapped[RiskLevel] = mapped_column(Enum(RiskLevel, name="action_risk_level"), nullable=False)
    status: Mapped[ActionStatus] = mapped_column(
        Enum(ActionStatus, name="action_status"),
        default=ActionStatus.PENDING,
        nullable=False,
    )

    # Structured parameters (never freeform)
    params: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)

    # Policy decision
    policy_decision: Mapped[str | None] = mapped_column(String(50), nullable=True)   # AUTO | APPROVAL | BLOCK
    policy_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Approval (for APPROVAL-gated actions)
    approved_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Execution result
    result: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    retry_count: Mapped[int] = mapped_column(default=0)

    # Verification
    verified: Mapped[bool] = mapped_column(Boolean, default=False)
    verification_result: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    commitment: Mapped["Commitment"] = relationship("Commitment", back_populates="actions")


# ─────────────────────────────────────────────────────────────────────────────
# TraceStep — per-commitment audit trail of every pipeline stage
# ─────────────────────────────────────────────────────────────────────────────

class TraceStep(Base):
    __tablename__ = "trace_steps"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid.uuid4()))
    commitment_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("commitments.id"), nullable=False)

    # Pipeline stage
    stage: Mapped[str] = mapped_column(String(50), nullable=False)   # OBSERVE, EXTRACT, RESOLVE, …
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    data: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)

    commitment: Mapped["Commitment"] = relationship("Commitment", back_populates="trace_steps")


# ─────────────────────────────────────────────────────────────────────────────
# PolicyRule — the human-editable policy table; LLM never modifies these
# ─────────────────────────────────────────────────────────────────────────────

class PolicyRule(Base):
    __tablename__ = "policy_rules"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid.uuid4()))
    action_type: Mapped[ActionType] = mapped_column(
        Enum(ActionType, name="policy_action_type"), nullable=False, unique=True
    )
    risk_level: Mapped[RiskLevel] = mapped_column(Enum(RiskLevel, name="policy_risk_level"), nullable=False)
    default_decision: Mapped[str] = mapped_column(String(50), nullable=False)   # AUTO | APPROVAL | BLOCK
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
