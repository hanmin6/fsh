from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import TypeDecorator

from mic_gateway.db.base import Base


def utc_now() -> datetime:
    return datetime.now(UTC)


class UTCDateTime(TypeDecorator[datetime]):
    """Store UTC in SQLite and always restore timezone-aware values."""

    impl = DateTime
    cache_ok = True

    def load_dialect_impl(self, dialect: Any) -> Any:
        return dialect.type_descriptor(DateTime(timezone=True))

    def process_bind_param(self, value: datetime | None, dialect: Any) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("datetime must be timezone-aware")
        return value.astimezone(UTC).replace(tzinfo=None)

    def process_result_value(self, value: datetime | None, dialect: Any) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)


class ApiKey(Base):
    __tablename__ = "api_keys"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    key_prefix: Mapped[str] = mapped_column(String(20), index=True)
    key_hash: Mapped[str] = mapped_column(Text)
    role: Mapped[str] = mapped_column(String(32), index=True)
    revoked: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now)


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    source_id: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    status: Mapped[str] = mapped_column(String(100), index=True)
    buyer_reference: Mapped[str | None] = mapped_column(String(255), index=True)
    currency: Mapped[str | None] = mapped_column(String(16))
    total_amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 4))
    source_created_at: Mapped[datetime] = mapped_column(UTCDateTime())
    source_updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), index=True)
    synced_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now)
    raw_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class OrderLine(Base):
    __tablename__ = "order_lines"
    __table_args__ = (UniqueConstraint("order_id", "source_line_id"),)

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    order_id: Mapped[UUID] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"), index=True)
    source_line_id: Mapped[str] = mapped_column(String(255))
    sku: Mapped[str | None] = mapped_column(String(255))
    name: Mapped[str] = mapped_column(Text)
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 4))
    unit_price: Mapped[Decimal | None] = mapped_column(Numeric(18, 4))
    raw_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    source_id: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    buyer_reference: Mapped[str | None] = mapped_column(String(255), index=True)
    inquiry_subject: Mapped[str | None] = mapped_column(Text)
    unread: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    last_message_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), index=True)
    source_updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), index=True)
    synced_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now)
    raw_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    history_complete: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")

    @property
    def buyer_name(self) -> str | None:
        if isinstance(self.raw_snapshot, dict):
            val = self.raw_snapshot.get("buyer_name") or self.raw_snapshot.get("contactName")
            if isinstance(val, str) and val.strip():
                return val.strip()
        return None

    @property
    def country(self) -> str | None:
        if isinstance(self.raw_snapshot, dict):
            val = (
                self.raw_snapshot.get("country")
                or self.raw_snapshot.get("regionName")
                or self.raw_snapshot.get("region")
            )
            if isinstance(val, str) and val.strip():
                return val.strip()
        return None


class SyncCheckpoint(Base):
    __tablename__ = "sync_checkpoints"

    resource: Mapped[str] = mapped_column(String(100), primary_key=True)
    source_cursor: Mapped[str | None] = mapped_column(Text)
    updated_after: Mapped[datetime | None] = mapped_column(UTCDateTime())
    overlap_seconds: Mapped[int] = mapped_column(Integer, default=600)
    last_attempt_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    last_success_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    failure_count: Mapped[int] = mapped_column(Integer, default=0)
    last_error_code: Mapped[str | None] = mapped_column(String(100))
    paused_reason: Mapped[str | None] = mapped_column(String(100))


class OutboxJob(Base):
    __tablename__ = "outbox_jobs"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    idempotency_key: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    payload_digest: Mapped[str] = mapped_column(String(64))
    conversation_id: Mapped[UUID] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"), index=True
    )
    intent: Mapped[str] = mapped_column(String(64))
    content: Mapped[str] = mapped_column(Text)
    caller_reference: Mapped[str | None] = mapped_column(String(255))
    caller_key_id: Mapped[UUID | None] = mapped_column(ForeignKey("api_keys.id"), index=True)
    request_id: Mapped[str] = mapped_column(String(64), index=True)
    state: Mapped[str] = mapped_column(String(32), index=True)
    attempt_count: Mapped[int] = mapped_column(Integer, default=0)
    next_attempt_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), index=True)
    attempted_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    sent_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    failure_code: Mapped[str | None] = mapped_column(String(100))
    safe_result_metadata: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), default=utc_now, onupdate=utc_now
    )


class Message(Base):
    __tablename__ = "messages"
    __table_args__ = (
        UniqueConstraint("conversation_id", "source_id"),
        UniqueConstraint("conversation_id", "fallback_fingerprint"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    source_id: Mapped[str | None] = mapped_column(String(255))
    fallback_fingerprint: Mapped[str] = mapped_column(String(64))
    conversation_id: Mapped[UUID] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"), index=True
    )
    direction: Mapped[str] = mapped_column(String(16), index=True)
    sender_label: Mapped[str | None] = mapped_column(String(255))
    content: Mapped[str] = mapped_column(Text)
    attachment_metadata: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    source_sequence: Mapped[int | None] = mapped_column(Integer)
    source_timestamp_raw: Mapped[str | None] = mapped_column(Text)
    source_timestamp_confidence: Mapped[str | None] = mapped_column(String(16))
    source_created_at: Mapped[datetime] = mapped_column(UTCDateTime(), index=True)
    synced_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now)
    outbound_job_id: Mapped[UUID | None] = mapped_column(ForeignKey("outbox_jobs.id"), index=True)
    raw_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    request_id: Mapped[str | None] = mapped_column(String(64), index=True)
    caller_key_id: Mapped[UUID | None] = mapped_column(ForeignKey("api_keys.id"), index=True)
    event_type: Mapped[str] = mapped_column(String(100), index=True)
    entity_type: Mapped[str | None] = mapped_column(String(100))
    entity_id: Mapped[str | None] = mapped_column(String(255), index=True)
    details: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now)


class RuntimeStatus(Base):
    __tablename__ = "runtime_status"

    component: Mapped[str] = mapped_column(String(100), primary_key=True)
    state: Mapped[str] = mapped_column(String(64), index=True)
    detail_code: Mapped[str | None] = mapped_column(String(100))
    last_transition_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), default=utc_now, onupdate=utc_now
    )
