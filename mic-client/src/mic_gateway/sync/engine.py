from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from mic_gateway.adapters.base import SiteAdapter, SourceCheckpoint
from mic_gateway.db.models import SyncCheckpoint
from mic_gateway.db.repositories import (
    CheckpointRepository,
    ConversationRepository,
    MessageRepository,
    OrderRepository,
)


def _utc_now() -> datetime:
    return datetime.now(UTC)


_SAFE_SITE_CONTRACT_REASONS = frozenset(
    {
        "message_list: inquiry missing or ambiguous",
        "message_list: messages must be an array",
        "message_list: attachList must be an array",
        "conversation_list: invalid isRead",
        "conversation_list: messages must be an array",
        "order_list: items must be an array",
        "order_list: unsuccessful response",
        "order_list_nonempty_unreviewed",
        "snapshot_sanitization_failed",
        "trademessenger_init_error",
        "trademessenger_history_incomplete",
        "trademessenger_history_incomplete: conversation missing",
        "trademessenger_history_incomplete: conversation identity unconfirmed",
        "trademessenger_history_incomplete: conversation identity changed",
        "trademessenger_history_incomplete: invalid chat markup",
        "trademessenger_history_incomplete: chat root missing",
        "trademessenger_history_incomplete: load control ambiguous",
        "trademessenger_history_incomplete: load control unrecognized",
        "trademessenger_history_incomplete: load control readiness unverified",
        "trademessenger_history_incomplete: history click bound reached",
        "trademessenger_history_incomplete: scroll bound reached",
        "trademessenger_history_incomplete: virtualized messages",
        "trademessenger_history_no_progress: load control made no progress",
        "trademessenger: no message bubbles",
        "trademessenger: unrecognized message direction",
        "trademessenger: message content missing",
        "trademessenger: empty message content",
        "trademessenger: message time missing",
        "trademessenger: no inbound or outbound bubbles",
    }
)


def safe_failure_code(error: Exception) -> str:
    name = type(error).__name__.casefold()
    if name == "sitecontracterror":
        reason = str(error)
        known_field_error = re.fullmatch(
            r"(?:message_list|conversation_list|order_list): "
            r"(?:invalid|missing|expected) [A-Za-z, ]+",
            reason,
        )
        if reason in _SAFE_SITE_CONTRACT_REASONS or (
            len(reason) <= 100 and known_field_error is not None
        ):
            return re.sub(r"[^a-z0-9]+", "_", reason.casefold()).strip("_")[:100]
    return name[:100]


def _require_aware(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("datetime must be timezone-aware")
    return value.astimezone(UTC)


def is_stale(
    last_success_at: datetime | None,
    now: datetime,
    *,
    threshold_seconds: int,
) -> bool:
    if last_success_at is None:
        return True
    if threshold_seconds <= 0:
        raise ValueError("threshold_seconds must be positive")
    return (_require_aware(now) - _require_aware(last_success_at)).total_seconds() > float(
        threshold_seconds
    )


@dataclass(frozen=True, slots=True)
class BackoffPolicy:
    base_seconds: int = 5
    maximum_seconds: int = 300

    def __post_init__(self) -> None:
        if self.base_seconds <= 0 or self.maximum_seconds < self.base_seconds:
            raise ValueError("backoff bounds are invalid")

    def next_delay(self, failure_count: int) -> int:
        delay = self.base_seconds
        for _ in range(max(0, failure_count - 1)):
            delay = min(self.maximum_seconds, delay * 2)
            if delay == self.maximum_seconds:
                break
        return delay


class SourceSessionUnavailable(RuntimeError):
    pass


class SyncEngine:
    def __init__(
        self,
        *,
        adapter: SiteAdapter,
        sessions: async_sessionmaker[AsyncSession],
        orders: OrderRepository,
        conversations: ConversationRepository,
        messages: MessageRepository,
        checkpoints: CheckpointRepository,
        overlap_seconds: int = 600,
        clock: Callable[[], datetime] = _utc_now,
    ) -> None:
        if overlap_seconds < 0:
            raise ValueError("overlap_seconds cannot be negative")
        self.adapter = adapter
        self.sessions = sessions
        self.orders = orders
        self.conversations = conversations
        self.messages = messages
        self.checkpoints = checkpoints
        self.overlap_seconds = overlap_seconds
        self.clock = clock

    async def _session_allows_work(
        self, resource: str, checkpoint: SyncCheckpoint | None
    ) -> bool:
        health = await self.adapter.check_session()
        if health.healthy:
            return True
        now = _require_aware(self.clock())
        if health.requires_operator:
            await self._save_checkpoint(
                resource,
                checkpoint,
                last_attempt_at=now,
                last_error_code=health.detail_code,
                paused_reason="operator_action_required",
            )
            return False
        error = SourceSessionUnavailable(health.detail_code or "source_session_unavailable")
        await self._record_failure(resource, checkpoint, error, attempted_at=now)
        raise error

    def _source_checkpoint(self, checkpoint: SyncCheckpoint | None) -> SourceCheckpoint:
        if checkpoint is None:
            return SourceCheckpoint(cursor=None, updated_after=None)
        updated_after = checkpoint.updated_after
        if checkpoint.source_cursor is None and updated_after is not None:
            updated_after -= timedelta(seconds=checkpoint.overlap_seconds)
        return SourceCheckpoint(
            cursor=checkpoint.source_cursor,
            updated_after=updated_after,
        )

    async def sync_orders(self) -> int:
        resource = "orders"
        checkpoint = await self.checkpoints.get(resource)
        if not await self._session_allows_work(resource, checkpoint):
            return 0
        attempted_at = _require_aware(self.clock())
        try:
            page = await self.adapter.list_orders(self._source_checkpoint(checkpoint))
            watermark = checkpoint.updated_after if checkpoint is not None else None
            if page.items:
                page_watermark = max(item.source_updated_at for item in page.items)
                watermark = max(
                    value for value in (watermark, page_watermark) if value is not None
                )
            async with self.sessions() as session, session.begin():
                for item in page.items:
                    await self.orders.upsert_in_session(session, item)
                await self.checkpoints.save_in_session(
                    session,
                    resource,
                    source_cursor=page.next_cursor,
                    updated_after=watermark,
                    overlap_seconds=(
                        checkpoint.overlap_seconds
                        if checkpoint is not None
                        else self.overlap_seconds
                    ),
                    last_attempt_at=attempted_at,
                    last_success_at=_require_aware(self.clock()),
                    failure_count=0,
                    last_error_code=None,
                    paused_reason=None,
                )
        except Exception as exc:
            await self._record_failure(resource, checkpoint, exc, attempted_at=attempted_at)
            raise
        return len(page.items)

    async def sync_conversations_and_messages(self) -> int:
        resource = "conversations"
        checkpoint = await self.checkpoints.get(resource)
        if not await self._session_allows_work(resource, checkpoint):
            return 0
        attempted_at = _require_aware(self.clock())
        try:
            page = await self.adapter.list_conversations(self._source_checkpoint(checkpoint))
            watermark = checkpoint.updated_after if checkpoint is not None else None
            if page.items:
                page_watermark = max(item.source_updated_at for item in page.items)
                watermark = max(
                    value for value in (watermark, page_watermark) if value is not None
                )
            async with self.sessions() as session, session.begin():
                for item in page.items:
                    await self.conversations.upsert_in_session(session, item)
                await self.checkpoints.save_in_session(
                    session,
                    resource,
                    source_cursor=page.next_cursor,
                    updated_after=watermark,
                    overlap_seconds=(
                        checkpoint.overlap_seconds
                        if checkpoint is not None
                        else self.overlap_seconds
                    ),
                    last_attempt_at=attempted_at,
                    last_success_at=_require_aware(self.clock()),
                    failure_count=0,
                    last_error_code=None,
                    paused_reason=None,
                )
        except Exception as exc:
            await self._record_failure(resource, checkpoint, exc, attempted_at=attempted_at)
            raise
        for item in page.items:
            await self._sync_messages(item.source_id)
        return len(page.items)

    async def _sync_messages(self, conversation_source_id: str) -> int:
        resource = f"messages:{conversation_source_id}"
        checkpoint = await self.checkpoints.get(resource)
        attempted_at = _require_aware(self.clock())
        try:
            page = await self.adapter.list_messages(
                conversation_source_id, self._source_checkpoint(checkpoint)
            )
            watermark = checkpoint.updated_after if checkpoint is not None else None
            if page.items:
                page_watermark = max(item.source_created_at for item in page.items)
                watermark = max(
                    value for value in (watermark, page_watermark) if value is not None
                )
            async with self.sessions() as session, session.begin():
                for item in page.items:
                    await self.messages.upsert_in_session(session, item)
                if page.history_complete:
                    await self.conversations.mark_history_complete_in_session(
                        session,
                        conversation_source_id,
                        buyer_name=page.buyer_name,
                        country=page.country,
                        buyer_id=page.buyer_id,
                    )
                elif page.buyer_name or page.country or page.buyer_id:
                    await self.conversations.update_profile_in_session(
                        session,
                        conversation_source_id,
                        buyer_name=page.buyer_name,
                        country=page.country,
                        buyer_id=page.buyer_id,
                    )
                await self.checkpoints.save_in_session(
                    session,
                    resource,
                    source_cursor=page.next_cursor,
                    updated_after=watermark,
                    overlap_seconds=(
                        checkpoint.overlap_seconds
                        if checkpoint is not None
                        else self.overlap_seconds
                    ),
                    last_attempt_at=attempted_at,
                    last_success_at=_require_aware(self.clock()),
                    failure_count=0,
                    last_error_code=None,
                    paused_reason=None,
                )
        except Exception as exc:
            await self._record_failure(resource, checkpoint, exc, attempted_at=attempted_at)
            raise
        return len(page.items)

    async def _record_failure(
        self,
        resource: str,
        checkpoint: SyncCheckpoint | None,
        error: Exception,
        *,
        attempted_at: datetime,
    ) -> None:
        await self._save_checkpoint(
            resource,
            checkpoint,
            last_attempt_at=attempted_at,
            failure_count=(checkpoint.failure_count if checkpoint is not None else 0) + 1,
            last_error_code=safe_failure_code(error),
        )

    async def _save_checkpoint(
        self,
        resource: str,
        checkpoint: SyncCheckpoint | None,
        *,
        last_attempt_at: datetime,
        failure_count: int | None = None,
        last_error_code: str | None = None,
        paused_reason: str | None = None,
    ) -> SyncCheckpoint:
        return await self.checkpoints.save(
            resource,
            source_cursor=checkpoint.source_cursor if checkpoint is not None else None,
            updated_after=checkpoint.updated_after if checkpoint is not None else None,
            overlap_seconds=(
                checkpoint.overlap_seconds if checkpoint is not None else self.overlap_seconds
            ),
            last_attempt_at=last_attempt_at,
            last_success_at=checkpoint.last_success_at if checkpoint is not None else None,
            failure_count=(
                failure_count
                if failure_count is not None
                else (checkpoint.failure_count if checkpoint is not None else 0)
            ),
            last_error_code=last_error_code,
            paused_reason=paused_reason,
        )
