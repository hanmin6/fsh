from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any
from uuid import UUID


class Role(StrEnum):
    CRM_READ = "crm_read"
    AGENT_SEND = "agent_send"
    ADMIN = "admin"


class MessageIntent(StrEnum):
    GREETING = "greeting"
    ACKNOWLEDGEMENT = "acknowledgement"
    HOLIDAY_WISH = "holiday_wish"
    NON_COMMERCIAL_FOLLOWUP = "non_commercial_followup"


class JobState(StrEnum):
    QUEUED = "queued"
    SENDING = "sending"
    SENT = "sent"
    REQUIRES_HUMAN_REVIEW = "requires_human_review"
    FAILED = "failed"
    UNCERTAIN = "uncertain"


class ServiceState(StrEnum):
    STARTING = "starting"
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    OPERATOR_ACTION_REQUIRED = "operator_action_required"
    SITE_CONTRACT_ERROR = "site_contract_error"
    STOPPED = "stopped"


class Direction(StrEnum):
    INBOUND = "inbound"
    OUTBOUND = "outbound"


def _require_aware(name: str, value: datetime | None) -> None:
    if value is not None and (value.tzinfo is None or value.utcoffset() is None):
        raise ValueError(f"{name} must be timezone-aware")


@dataclass(frozen=True, slots=True)
class SourceOrderLine:
    source_line_id: str
    sku: str | None
    name: str
    quantity: Decimal
    unit_price: Decimal | None
    raw_snapshot: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class SourceOrder:
    source_id: str
    status: str
    buyer_reference: str | None
    currency: str | None
    total_amount: Decimal | None
    source_created_at: datetime
    source_updated_at: datetime
    lines: tuple[SourceOrderLine, ...] = ()
    raw_snapshot: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require_aware("source_created_at", self.source_created_at)
        _require_aware("source_updated_at", self.source_updated_at)


@dataclass(frozen=True, slots=True)
class SourceConversation:
    source_id: str
    buyer_reference: str | None
    inquiry_subject: str | None
    unread: bool
    last_message_at: datetime | None
    source_updated_at: datetime
    raw_snapshot: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require_aware("last_message_at", self.last_message_at)
        _require_aware("source_updated_at", self.source_updated_at)


@dataclass(frozen=True, slots=True)
class SourceMessage:
    source_id: str | None
    conversation_source_id: str
    direction: Direction
    sender_label: str | None
    content: str
    attachment_metadata: tuple[dict[str, Any], ...]
    source_created_at: datetime
    raw_snapshot: dict[str, Any] = field(default_factory=dict)
    source_timestamp_raw: str | None = None
    source_sequence: int | None = None
    source_timestamp_confidence: str | None = None

    def __post_init__(self) -> None:
        _require_aware("source_created_at", self.source_created_at)
        if self.source_sequence is not None and self.source_sequence < 1:
            raise ValueError("source_sequence must be positive")
        if self.source_timestamp_confidence not in {None, "high", "medium", "low"}:
            raise ValueError("source_timestamp_confidence must be high, medium, low, or None")


@dataclass(frozen=True, slots=True)
class OutboxCreateRequest:
    idempotency_key: str
    payload_digest: str
    conversation_id: UUID
    intent: MessageIntent
    content: str
    caller_reference: str | None
    caller_key_id: UUID | None
    request_id: str
    initial_state: JobState = JobState.QUEUED
