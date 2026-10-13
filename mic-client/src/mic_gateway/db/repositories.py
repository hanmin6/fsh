from __future__ import annotations

import base64
import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, cast
from uuid import UUID, uuid4

from sqlalchemy import case, delete, func, or_, select, update
from sqlalchemy.dialects.sqlite import insert
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from mic_gateway.db.models import (
    AuditEvent,
    Conversation,
    Message,
    Order,
    OrderLine,
    OutboxJob,
    SyncCheckpoint,
    utc_now,
)
from mic_gateway.domain import (
    OutboxCreateRequest,
    SourceConversation,
    SourceMessage,
    SourceOrder,
)
from mic_gateway.errors import ApiError

_SENSITIVE_KEY_PARTS = ("authorization", "cookie", "password", "session", "token")


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("datetime must be timezone-aware")
    return value.astimezone(UTC)


def encode_cursor(updated_at: datetime, row_id: UUID) -> str:
    payload = {
        "u": _as_utc(updated_at).isoformat(),
        "i": str(row_id),
    }
    raw = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def decode_cursor(value: str) -> tuple[datetime, UUID]:
    try:
        padded = value + "=" * (-len(value) % 4)
        payload = json.loads(base64.b64decode(padded, altchars=b"-_", validate=True))
        if not isinstance(payload, dict) or set(payload) != {"u", "i"}:
            raise ValueError("unexpected cursor shape")
        if not isinstance(payload["u"], str) or not isinstance(payload["i"], str):
            raise ValueError("cursor fields must be strings")
        updated_at = datetime.fromisoformat(payload["u"])
        updated_at = _as_utc(updated_at)
        row_id = UUID(payload["i"])
    except (ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
        raise ApiError(422, "invalid_cursor", "The pagination cursor is invalid.") from exc
    return updated_at, row_id


def _encode_message_cursor(message: Message) -> str:
    payload = {
        "s": message.source_sequence,
        "u": _as_utc(message.source_created_at).isoformat(),
        "i": str(message.id),
    }
    raw = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def _decode_message_cursor(value: str) -> tuple[int | None, datetime, UUID, bool]:
    """Decode source-order cursors and legacy time/ID cursors."""
    try:
        padded = value + "=" * (-len(value) % 4)
        payload = json.loads(base64.b64decode(padded, altchars=b"-_", validate=True))
        if not isinstance(payload, dict):
            raise ValueError("unexpected cursor shape")
        legacy = set(payload) == {"u", "i"}
        if legacy:
            sequence = None
        elif set(payload) == {"s", "u", "i"}:
            sequence = payload["s"]
            if sequence is not None and (not isinstance(sequence, int) or sequence < 1):
                raise ValueError("invalid source sequence")
        else:
            raise ValueError("unexpected cursor shape")
        if not isinstance(payload["u"], str) or not isinstance(payload["i"], str):
            raise ValueError("cursor fields must be strings")
        updated_at = _as_utc(datetime.fromisoformat(payload["u"]))
        row_id = UUID(payload["i"])
    except (ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
        raise ApiError(422, "invalid_cursor", "The pagination cursor is invalid.") from exc
    return sequence, updated_at, row_id, legacy


def sanitize_snapshot(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            str(key): (
                "[REDACTED]"
                if any(part in str(key).casefold() for part in _SENSITIVE_KEY_PARTS)
                else sanitize_snapshot(item)
            )
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [sanitize_snapshot(item) for item in value]
    if isinstance(value, tuple):
        return [sanitize_snapshot(item) for item in value]
    return value


class OrderRepository:
    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self._sessions = sessions

    async def upsert(self, source: SourceOrder) -> Order:
        async with self._sessions() as session, session.begin():
            return await self.upsert_in_session(session, source)

    async def upsert_in_session(self, session: AsyncSession, source: SourceOrder) -> Order:
        values = {
            "id": uuid4(),
            "source_id": source.source_id,
            "status": source.status,
            "buyer_reference": source.buyer_reference,
            "currency": source.currency,
            "total_amount": source.total_amount,
            "source_created_at": source.source_created_at,
            "source_updated_at": source.source_updated_at,
            "synced_at": utc_now(),
            "raw_snapshot": sanitize_snapshot(source.raw_snapshot),
        }
        statement = insert(Order).values(**values)
        statement = statement.on_conflict_do_update(
            index_elements=[Order.source_id],
            set_={
                "status": statement.excluded.status,
                "buyer_reference": statement.excluded.buyer_reference,
                "currency": statement.excluded.currency,
                "total_amount": statement.excluded.total_amount,
                "source_created_at": statement.excluded.source_created_at,
                "source_updated_at": statement.excluded.source_updated_at,
                "synced_at": statement.excluded.synced_at,
                "raw_snapshot": statement.excluded.raw_snapshot,
            },
            where=statement.excluded.source_updated_at >= Order.source_updated_at,
        )

        await session.execute(statement)
        order = await self._get_by_source_id(session, source.source_id)
        if order.source_updated_at == _as_utc(source.source_updated_at):
            await session.execute(delete(OrderLine).where(OrderLine.order_id == order.id))
            for line in source.lines:
                session.add(
                    OrderLine(
                        order_id=order.id,
                        source_line_id=line.source_line_id,
                        sku=line.sku,
                        name=line.name,
                        quantity=line.quantity,
                        unit_price=line.unit_price,
                        raw_snapshot=sanitize_snapshot(line.raw_snapshot),
                    )
                )
        await session.flush()
        await session.refresh(order)
        return order

    async def _get_by_source_id(self, session: AsyncSession, source_id: str) -> Order:
        result = await session.execute(select(Order).where(Order.source_id == source_id))
        return result.scalar_one()

    async def get(self, order_id: UUID) -> Order | None:
        async with self._sessions() as session:
            return await session.get(Order, order_id)

    async def get_by_source_id(self, source_id: str) -> Order | None:
        async with self._sessions() as session:
            result = await session.execute(select(Order).where(Order.source_id == source_id))
            return result.scalar_one_or_none()

    async def count(self) -> int:
        async with self._sessions() as session:
            return int(await session.scalar(select(func.count()).select_from(Order)) or 0)

    async def list_lines(self, order_id: UUID) -> list[OrderLine]:
        query = (
            select(OrderLine)
            .where(OrderLine.order_id == order_id)
            .order_by(OrderLine.source_line_id.asc(), OrderLine.id.asc())
        )
        async with self._sessions() as session:
            return list((await session.scalars(query)).all())

    async def list_page(
        self,
        *,
        limit: int,
        cursor: str | None = None,
        updated_after: datetime | None = None,
        status: str | None = None,
        buyer_reference: str | None = None,
    ) -> tuple[list[Order], str | None]:
        query = select(Order)
        if cursor is not None:
            cursor_time, cursor_id = decode_cursor(cursor)
            query = query.where(
                or_(
                    Order.source_updated_at < cursor_time,
                    (Order.source_updated_at == cursor_time) & (Order.id < cursor_id),
                )
            )
        if updated_after is not None:
            query = query.where(Order.source_updated_at >= _as_utc(updated_after))
        if status is not None:
            query = query.where(Order.status == status)
        if buyer_reference is not None:
            query = query.where(Order.buyer_reference == buyer_reference)
        query = query.order_by(Order.source_updated_at.desc(), Order.id.desc()).limit(limit + 1)
        async with self._sessions() as session:
            rows = list((await session.scalars(query)).all())
        has_more = len(rows) > limit
        rows = rows[:limit]
        next_cursor = (
            encode_cursor(rows[-1].source_updated_at, rows[-1].id)
            if has_more and rows
            else None
        )
        return rows, next_cursor


class ConversationRepository:
    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self._sessions = sessions

    async def upsert(self, source: SourceConversation) -> Conversation:
        async with self._sessions() as session, session.begin():
            return await self.upsert_in_session(session, source)

    async def upsert_in_session(
        self, session: AsyncSession, source: SourceConversation
    ) -> Conversation:
        existing = await session.scalar(
            select(Conversation).where(Conversation.source_id == source.source_id)
        )
        new_snapshot = sanitize_snapshot(source.raw_snapshot)
        if existing and isinstance(existing.raw_snapshot, dict):
            for k in ("buyer_name", "country", "buyer_id"):
                if existing.raw_snapshot.get(k) and not new_snapshot.get(k):
                    new_snapshot[k] = existing.raw_snapshot[k]
        values = {
            "id": uuid4(),
            "source_id": source.source_id,
            # Inquiry lists may report the seller contact ID. A buyer ID read
            # from this conversation's detail page remains authoritative.
            "buyer_reference": new_snapshot.get("buyer_id") or source.buyer_reference,
            "inquiry_subject": source.inquiry_subject,
            "unread": source.unread,
            "last_message_at": source.last_message_at,
            "source_updated_at": source.source_updated_at,
            "synced_at": utc_now(),
            "raw_snapshot": new_snapshot,
        }
        statement = insert(Conversation).values(**values)
        statement = statement.on_conflict_do_update(
            index_elements=[Conversation.source_id],
            set_={
                "buyer_reference": statement.excluded.buyer_reference,
                "inquiry_subject": statement.excluded.inquiry_subject,
                "unread": statement.excluded.unread,
                "last_message_at": statement.excluded.last_message_at,
                "source_updated_at": statement.excluded.source_updated_at,
                "synced_at": statement.excluded.synced_at,
                "raw_snapshot": statement.excluded.raw_snapshot,
                "history_complete": case(
                    (
                        statement.excluded.source_updated_at > Conversation.source_updated_at,
                        False,
                    ),
                    else_=Conversation.history_complete,
                ),
            },
            where=statement.excluded.source_updated_at >= Conversation.source_updated_at,
        )
        await session.execute(statement)
        result = await session.execute(
            select(Conversation).where(Conversation.source_id == source.source_id)
        )
        conversation = result.scalar_one()
        await session.refresh(conversation)
        return conversation

    async def get(self, conversation_id: UUID) -> Conversation | None:
        async with self._sessions() as session:
            return await session.get(Conversation, conversation_id)

    async def get_by_source_id(self, source_id: str) -> Conversation | None:
        async with self._sessions() as session:
            result = await session.execute(
                select(Conversation).where(Conversation.source_id == source_id)
            )
            return result.scalar_one_or_none()

    async def mark_history_complete_in_session(
        self,
        session: AsyncSession,
        source_id: str,
        *,
        buyer_name: str | None = None,
        country: str | None = None,
        buyer_id: str | None = None,
    ) -> None:
        conversation = await session.scalar(
            select(Conversation).where(Conversation.source_id == source_id)
        )
        if conversation is None:
            raise RuntimeError("cannot complete history for an unknown conversation")
        conversation.history_complete = True
        snapshot = dict(conversation.raw_snapshot or {})
        updated = False
        if buyer_id:
            conversation.buyer_reference = buyer_id
            snapshot["buyer_id"] = buyer_id
            updated = True
        elif conversation.buyer_reference == "EEnxEJQbMJmm":
            conversation.buyer_reference = source_id
            snapshot["buyer_id"] = source_id
            updated = True
        if buyer_name and snapshot.get("buyer_name") != buyer_name:
            snapshot["buyer_name"] = buyer_name
            updated = True
        if country and snapshot.get("country") != country:
            snapshot["country"] = country
            updated = True
        if updated:
            conversation.raw_snapshot = snapshot

    async def update_profile_in_session(
        self,
        session: AsyncSession,
        source_id: str,
        *,
        buyer_name: str | None = None,
        country: str | None = None,
        buyer_id: str | None = None,
    ) -> None:
        conversation = await session.scalar(
            select(Conversation).where(Conversation.source_id == source_id)
        )
        if conversation is None:
            return
        snapshot = dict(conversation.raw_snapshot or {})
        updated = False
        if buyer_id:
            conversation.buyer_reference = buyer_id
            snapshot["buyer_id"] = buyer_id
            updated = True
        elif conversation.buyer_reference == "EEnxEJQbMJmm":
            conversation.buyer_reference = source_id
            snapshot["buyer_id"] = source_id
            updated = True
        if buyer_name and snapshot.get("buyer_name") != buyer_name:
            snapshot["buyer_name"] = buyer_name
            updated = True
        if country and snapshot.get("country") != country:
            snapshot["country"] = country
            updated = True
        if updated:
            conversation.raw_snapshot = snapshot

    async def count(self) -> int:
        async with self._sessions() as session:
            return int(await session.scalar(select(func.count()).select_from(Conversation)) or 0)

    async def list_page(
        self,
        *,
        limit: int,
        cursor: str | None = None,
        updated_after: datetime | None = None,
        unread: bool | None = None,
        buyer_reference: str | None = None,
    ) -> tuple[list[Conversation], str | None]:
        query = select(Conversation)
        if cursor is not None:
            cursor_time, cursor_id = decode_cursor(cursor)
            query = query.where(
                or_(
                    Conversation.source_updated_at < cursor_time,
                    (Conversation.source_updated_at == cursor_time)
                    & (Conversation.id < cursor_id),
                )
            )
        if updated_after is not None:
            query = query.where(Conversation.source_updated_at >= _as_utc(updated_after))
        if unread is not None:
            query = query.where(Conversation.unread == unread)
        if buyer_reference is not None:
            query = query.where(Conversation.buyer_reference == buyer_reference)
        query = query.order_by(
            Conversation.source_updated_at.desc(), Conversation.id.desc()
        ).limit(limit + 1)
        async with self._sessions() as session:
            rows = list((await session.scalars(query)).all())
        has_more = len(rows) > limit
        rows = rows[:limit]
        next_cursor = (
            encode_cursor(rows[-1].source_updated_at, rows[-1].id)
            if has_more and rows
            else None
        )
        return rows, next_cursor


class MessageRepository:
    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self._sessions = sessions

    @staticmethod
    def fingerprint(source: SourceMessage) -> str:
        payload = {
            "conversation_source_id": source.conversation_source_id,
            "direction": source.direction.value,
            "sender_label": source.sender_label,
            "content": source.content,
            "source_created_at": _as_utc(source.source_created_at).isoformat(),
            "attachment_metadata": sanitize_snapshot(source.attachment_metadata),
            "source_sequence": source.source_sequence,
            "source_timestamp_raw": source.source_timestamp_raw,
        }
        canonical = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
        return hashlib.sha256(canonical).hexdigest()

    async def upsert(self, source: SourceMessage) -> Message:
        async with self._sessions() as session, session.begin():
            return await self.upsert_in_session(session, source)

    async def upsert_in_session(
        self, session: AsyncSession, source: SourceMessage
    ) -> Message:
        fingerprint = self.fingerprint(source)
        conversation_id = await session.scalar(
            select(Conversation.id).where(
                Conversation.source_id == source.conversation_source_id
            )
        )
        if conversation_id is None:
            raise ApiError(422, "unknown_conversation", "The conversation is not synced.")
        values = {
            "id": uuid4(),
            "source_id": source.source_id,
            "fallback_fingerprint": fingerprint,
            "conversation_id": conversation_id,
            "direction": source.direction.value,
            "sender_label": source.sender_label,
            "content": source.content,
            "attachment_metadata": sanitize_snapshot(source.attachment_metadata),
            "source_sequence": source.source_sequence,
            "source_timestamp_raw": source.source_timestamp_raw,
            "source_timestamp_confidence": source.source_timestamp_confidence,
            "source_created_at": source.source_created_at,
            "synced_at": utc_now(),
            "raw_snapshot": sanitize_snapshot(source.raw_snapshot),
        }
        statement = insert(Message).values(**values)
        conflict_columns = (
            [Message.conversation_id, Message.source_id]
            if source.source_id is not None
            else [Message.conversation_id, Message.fallback_fingerprint]
        )
        statement = statement.on_conflict_do_update(
            index_elements=conflict_columns,
            set_={
                "direction": statement.excluded.direction,
                "sender_label": statement.excluded.sender_label,
                "content": statement.excluded.content,
                "attachment_metadata": statement.excluded.attachment_metadata,
                "source_sequence": func.coalesce(
                    statement.excluded.source_sequence, Message.source_sequence
                ),
                "source_timestamp_raw": func.coalesce(
                    statement.excluded.source_timestamp_raw, Message.source_timestamp_raw
                ),
                "source_timestamp_confidence": func.coalesce(
                    statement.excluded.source_timestamp_confidence,
                    Message.source_timestamp_confidence,
                ),
                "source_created_at": statement.excluded.source_created_at,
                "synced_at": statement.excluded.synced_at,
                "raw_snapshot": statement.excluded.raw_snapshot,
            },
        )
        await session.execute(statement)
        identity_filter = (
            Message.source_id == source.source_id
            if source.source_id is not None
            else Message.fallback_fingerprint == fingerprint
        )
        result = await session.execute(
            select(Message).where(
                Message.conversation_id == conversation_id, identity_filter
            )
        )
        message = result.scalar_one()
        await session.refresh(message)
        return message

    async def count(self) -> int:
        async with self._sessions() as session:
            return int(await session.scalar(select(func.count()).select_from(Message)) or 0)

    async def list_for_conversation(
        self, conversation_id: UUID, *, limit: int = 100
    ) -> list[Message]:
        query = (
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(
                Message.source_sequence.asc().nulls_last(),
                Message.source_created_at.asc(),
                Message.id.asc(),
            )
            .limit(limit)
        )
        async with self._sessions() as session:
            return list((await session.scalars(query)).all())

    async def list_page_for_conversation(
        self,
        conversation_id: UUID,
        *,
        limit: int,
        cursor: str | None = None,
    ) -> tuple[list[Message], str | None]:
        query = select(Message).where(Message.conversation_id == conversation_id)
        legacy_cursor = False
        if cursor is not None:
            cursor_sequence, cursor_time, cursor_id, legacy_cursor = _decode_message_cursor(
                cursor
            )
            after_time_and_id = or_(
                Message.source_created_at > cursor_time,
                (Message.source_created_at == cursor_time) & (Message.id > cursor_id),
            )
            if legacy_cursor:
                # Previously issued cursors were based on timestamp and UUID order.
                query = query.where(after_time_and_id)
            elif cursor_sequence is None:
                query = query.where(
                    Message.source_sequence.is_(None), after_time_and_id
                )
            else:
                query = query.where(
                    or_(
                        Message.source_sequence > cursor_sequence,
                        (Message.source_sequence == cursor_sequence) & after_time_and_id,
                        Message.source_sequence.is_(None),
                    )
                )
        if legacy_cursor:
            query = query.order_by(Message.source_created_at.asc(), Message.id.asc())
        else:
            query = query.order_by(
                Message.source_sequence.asc().nulls_last(),
                Message.source_created_at.asc(),
                Message.id.asc(),
            )
        query = query.limit(limit + 1)
        async with self._sessions() as session:
            rows = list((await session.scalars(query)).all())
        has_more = len(rows) > limit
        rows = rows[:limit]
        next_cursor = (
            (
                encode_cursor(rows[-1].source_created_at, rows[-1].id)
                if legacy_cursor
                else _encode_message_cursor(rows[-1])
            )
            if has_more and rows
            else None
        )
        return rows, next_cursor


class CheckpointRepository:
    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self._sessions = sessions

    async def get(self, resource: str) -> SyncCheckpoint | None:
        async with self._sessions() as session:
            return await session.get(SyncCheckpoint, resource)

    async def save(
        self,
        resource: str,
        *,
        source_cursor: str | None = None,
        updated_after: datetime | None = None,
        overlap_seconds: int = 600,
        last_attempt_at: datetime | None = None,
        last_success_at: datetime | None = None,
        failure_count: int = 0,
        last_error_code: str | None = None,
        paused_reason: str | None = None,
    ) -> SyncCheckpoint:
        async with self._sessions() as session, session.begin():
            return await self.save_in_session(
                session,
                resource,
                source_cursor=source_cursor,
                updated_after=updated_after,
                overlap_seconds=overlap_seconds,
                last_attempt_at=last_attempt_at,
                last_success_at=last_success_at,
                failure_count=failure_count,
                last_error_code=last_error_code,
                paused_reason=paused_reason,
            )

    async def save_in_session(
        self,
        session: AsyncSession,
        resource: str,
        *,
        source_cursor: str | None = None,
        updated_after: datetime | None = None,
        overlap_seconds: int = 600,
        last_attempt_at: datetime | None = None,
        last_success_at: datetime | None = None,
        failure_count: int = 0,
        last_error_code: str | None = None,
        paused_reason: str | None = None,
    ) -> SyncCheckpoint:
        values = {
            "resource": resource,
            "source_cursor": source_cursor,
            "updated_after": updated_after,
            "overlap_seconds": overlap_seconds,
            "last_attempt_at": last_attempt_at,
            "last_success_at": last_success_at,
            "failure_count": failure_count,
            "last_error_code": last_error_code,
            "paused_reason": paused_reason,
        }
        statement = insert(SyncCheckpoint).values(**values)
        statement = statement.on_conflict_do_update(
            index_elements=[SyncCheckpoint.resource],
            set_={key: getattr(statement.excluded, key) for key in values if key != "resource"},
        )
        await session.execute(statement)
        checkpoint = await session.get(SyncCheckpoint, resource)
        if checkpoint is None:  # pragma: no cover - guarded by the upsert
            raise RuntimeError("checkpoint upsert did not persist")
        await session.refresh(checkpoint)
        return checkpoint


@dataclass(frozen=True, slots=True)
class OutboxCreateResult:
    job: OutboxJob
    created: bool


class OutboxRepository:
    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self._sessions = sessions

    async def create_idempotent(self, request: OutboxCreateRequest) -> OutboxCreateResult:
        values = {
            "id": uuid4(),
            "idempotency_key": request.idempotency_key,
            "payload_digest": request.payload_digest,
            "conversation_id": request.conversation_id,
            "intent": request.intent.value,
            "content": request.content,
            "caller_reference": request.caller_reference,
            "caller_key_id": request.caller_key_id,
            "request_id": request.request_id,
            "state": request.initial_state.value,
            "attempt_count": 0,
            "safe_result_metadata": {},
            "created_at": utc_now(),
            "updated_at": utc_now(),
        }
        statement = (
            insert(OutboxJob)
            .values(**values)
            .on_conflict_do_nothing(index_elements=[OutboxJob.idempotency_key])
        )
        async with self._sessions() as session, session.begin():
            result = await session.execute(statement)
            created = cast(CursorResult[Any], result).rowcount == 1
            selected = await session.execute(
                select(OutboxJob).where(
                    OutboxJob.idempotency_key == request.idempotency_key
                )
            )
            job = selected.scalar_one()
            if job.payload_digest != request.payload_digest:
                raise ApiError(
                    409,
                    "idempotency_conflict",
                    "The idempotency key was already used for a different payload.",
                )
            return OutboxCreateResult(job=job, created=created)

    async def get(self, job_id: UUID) -> OutboxJob | None:
        async with self._sessions() as session:
            return await session.get(OutboxJob, job_id)

    async def count(self) -> int:
        async with self._sessions() as session:
            return int(await session.scalar(select(func.count()).select_from(OutboxJob)) or 0)

    async def claim_next(self, now: datetime) -> OutboxJob | None:
        now = _as_utc(now)
        async with self._sessions() as session, session.begin():
            candidate_id = await session.scalar(
                select(OutboxJob.id)
                .where(
                    OutboxJob.state == "queued",
                    or_(
                        OutboxJob.next_attempt_at.is_(None),
                        OutboxJob.next_attempt_at <= now,
                    ),
                )
                .order_by(OutboxJob.created_at.asc(), OutboxJob.id.asc())
                .limit(1)
            )
            if candidate_id is None:
                return None
            result = await session.execute(
                update(OutboxJob)
                .where(OutboxJob.id == candidate_id, OutboxJob.state == "queued")
                .values(
                    state="sending",
                    attempt_count=OutboxJob.attempt_count + 1,
                    attempted_at=now,
                    next_attempt_at=None,
                    updated_at=now,
                )
            )
            if cast(CursorResult[Any], result).rowcount != 1:
                return None
            job = await session.get(OutboxJob, candidate_id)
            if job is None:  # pragma: no cover - guarded by the conditional update
                return None
            self._add_transition_audit(session, job, "queued", "sending")
            await session.flush()
            await session.refresh(job)
            return job

    async def transition(
        self,
        job_id: UUID,
        *,
        expected_state: str,
        new_state: str,
        now: datetime,
        failure_code: str | None = None,
        next_attempt_at: datetime | None = None,
        sent_at: datetime | None = None,
        safe_result_metadata: dict[str, Any] | None = None,
    ) -> OutboxJob | None:
        async with self._sessions() as session, session.begin():
            job = await session.get(OutboxJob, job_id)
            if job is None or job.state != expected_state:
                return None
            old_state = job.state
            job.state = new_state
            job.failure_code = failure_code
            job.next_attempt_at = next_attempt_at
            job.sent_at = sent_at
            job.updated_at = _as_utc(now)
            if safe_result_metadata is not None:
                job.safe_result_metadata = sanitize_snapshot(safe_result_metadata)
            self._add_transition_audit(session, job, old_state, new_state)
            await session.flush()
            await session.refresh(job)
            return job

    async def recover_sending(self, now: datetime) -> int:
        async with self._sessions() as session, session.begin():
            jobs = list(
                (
                    await session.scalars(
                        select(OutboxJob).where(OutboxJob.state == "sending")
                    )
                ).all()
            )
            for job in jobs:
                job.state = "uncertain"
                job.failure_code = "process_restart"
                job.updated_at = _as_utc(now)
                self._add_transition_audit(session, job, "sending", "uncertain")
            await session.flush()
            return len(jobs)

    async def conversation_source_id(self, conversation_id: UUID) -> str | None:
        async with self._sessions() as session:
            value: str | None = await session.scalar(
                select(Conversation.source_id).where(Conversation.id == conversation_id)
            )
            return value

    @staticmethod
    def _add_transition_audit(
        session: AsyncSession,
        job: OutboxJob,
        old_state: str,
        new_state: str,
    ) -> None:
        session.add(
            AuditEvent(
                request_id=job.request_id,
                caller_key_id=job.caller_key_id,
                event_type="outbox_state_transition",
                entity_type="outbox_job",
                entity_id=str(job.id),
                details={
                    "from": old_state,
                    "to": new_state,
                    "failure_code": job.failure_code,
                },
            )
        )
