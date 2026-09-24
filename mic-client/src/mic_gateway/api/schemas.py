from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from mic_gateway.domain import Direction, JobState, MessageIntent


class PublicModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class ErrorDetail(BaseModel):
    code: str
    message: str
    request_id: str


class ErrorResponse(BaseModel):
    error: ErrorDetail


class OrderLineResponse(PublicModel):
    id: UUID
    source_line_id: str
    sku: str | None
    name: str
    quantity: Decimal
    unit_price: Decimal | None


class OrderResponse(PublicModel):
    id: UUID
    source_id: str
    status: str
    buyer_reference: str | None
    currency: str | None
    total_amount: Decimal | None
    source_created_at: datetime
    source_updated_at: datetime
    synced_at: datetime
    lines: list[OrderLineResponse] = Field(default_factory=list)


class ConversationResponse(PublicModel):
    id: UUID
    source_id: str
    buyer_reference: str | None
    inquiry_subject: str | None
    unread: bool
    last_message_at: datetime | None
    source_updated_at: datetime
    synced_at: datetime
    history_complete: bool = False
    buyer_name: str | None = None
    country: str | None = None


class MessageResponse(PublicModel):
    id: UUID
    source_id: str | None
    conversation_id: UUID
    direction: Direction
    sender_label: str | None
    content: str
    attachment_metadata: list[dict[str, object]]
    source_sequence: int | None
    source_timestamp_raw: str | None
    source_timestamp_confidence: Literal["high", "medium", "low"] | None
    source_created_at: datetime
    synced_at: datetime
    outbound_job_id: UUID | None


class JobResponse(PublicModel):
    id: UUID
    conversation_id: UUID
    intent: MessageIntent
    caller_reference: str | None
    request_id: str
    state: JobState
    attempt_count: int
    next_attempt_at: datetime | None
    attempted_at: datetime | None
    sent_at: datetime | None
    failure_code: str | None
    safe_result_metadata: dict[str, object]
    created_at: datetime
    updated_at: datetime


class MessageSubmitRequest(BaseModel):
    idempotency_key: Annotated[
        str,
        StringConstraints(strip_whitespace=True, min_length=1, max_length=128),
    ]
    intent: MessageIntent
    content: Annotated[str, StringConstraints(min_length=1, max_length=4_000)]
    caller_reference: Annotated[
        str,
        StringConstraints(strip_whitespace=True, min_length=1, max_length=255),
    ] | None = None


class ManualSyncRequest(BaseModel):
    resource: Literal["orders", "conversations", "all"]


class ManualSyncResponse(BaseModel):
    queued: bool
    resource: str


class CursorPage[T](BaseModel):
    items: list[T]
    next_cursor: str | None
