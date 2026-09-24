from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest
import pytest_asyncio
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from mic_gateway.adapters.base import SessionHealth, SourcePage
from mic_gateway.adapters.fake import FakeSiteAdapter
from mic_gateway.config import Settings
from mic_gateway.db.base import Base, create_engine_and_sessionmaker
from mic_gateway.db.repositories import (
    CheckpointRepository,
    ConversationRepository,
    MessageRepository,
    OrderRepository,
)
from mic_gateway.domain import (
    Direction,
    SourceConversation,
    SourceMessage,
    SourceOrder,
    SourceOrderLine,
)
from mic_gateway.sync.engine import BackoffPolicy, SyncEngine, is_stale


@pytest_asyncio.fixture
async def sessions(tmp_path: Path) -> async_sessionmaker[AsyncSession]:
    settings = Settings(
        app_data_dir=tmp_path,
        database_url=f"sqlite+aiosqlite:///{(tmp_path / 'sync.db').as_posix()}",
    )
    engine, factory = create_engine_and_sessionmaker(settings)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    try:
        yield factory
    finally:
        await engine.dispose()


def order(source_id: str, updated_at: datetime, status: str) -> SourceOrder:
    return SourceOrder(
        source_id=source_id,
        status=status,
        buyer_reference="buyer-1",
        currency="USD",
        total_amount=Decimal("25"),
        source_created_at=updated_at - timedelta(days=1),
        source_updated_at=updated_at,
        lines=(
            SourceOrderLine(
                source_line_id=f"{source_id}-line",
                sku="SKU-1",
                name="Widget",
                quantity=Decimal("1"),
                unit_price=Decimal("25"),
            ),
        ),
    )


def make_engine(
    sessions: async_sessionmaker[AsyncSession], adapter: FakeSiteAdapter
) -> SyncEngine:
    return SyncEngine(
        adapter=adapter,
        sessions=sessions,
        orders=OrderRepository(sessions),
        conversations=ConversationRepository(sessions),
        messages=MessageRepository(sessions),
        checkpoints=CheckpointRepository(sessions),
    )


@pytest.mark.asyncio
async def test_restart_resumes_from_committed_checkpoint(
    sessions: async_sessionmaker[AsyncSession],
) -> None:
    now = datetime(2026, 9, 19, 12, 0, tzinfo=UTC)
    adapter = FakeSiteAdapter(
        order_pages={
            None: SourcePage(items=(order("order-1", now, "new"),), next_cursor="page-2"),
            "page-2": SourcePage(
                items=(order("order-2", now + timedelta(minutes=1), "paid"),),
                next_cursor=None,
            ),
        }
    )

    await make_engine(sessions, adapter).sync_orders()
    await make_engine(sessions, adapter).sync_orders()

    assert [item.cursor for item in adapter.order_checkpoints] == [None, "page-2"]
    assert await OrderRepository(sessions).count() == 2


@pytest.mark.asyncio
async def test_older_overlap_record_does_not_replace_newer_row(
    sessions: async_sessionmaker[AsyncSession],
) -> None:
    now = datetime(2026, 9, 19, 12, 0, tzinfo=UTC)
    adapter = FakeSiteAdapter(
        order_pages={None: SourcePage(items=(order("order-1", now, "newer"),), next_cursor=None)}
    )
    engine = make_engine(sessions, adapter)
    await engine.sync_orders()
    adapter.order_pages[None] = SourcePage(
        items=(order("order-1", now - timedelta(minutes=5), "older"),),
        next_cursor=None,
    )

    await engine.sync_orders()

    stored = await OrderRepository(sessions).get_by_source_id("order-1")
    assert stored is not None
    assert stored.status == "newer"
    assert adapter.order_checkpoints[-1].updated_after == now - timedelta(minutes=10)


@pytest.mark.asyncio
async def test_page_failure_rolls_back_rows_before_recording_failure(
    sessions: async_sessionmaker[AsyncSession],
) -> None:
    now = datetime(2026, 9, 19, 12, 0, tzinfo=UTC)
    valid = order("order-1", now, "new")
    invalid = replace(order("order-2", now, "new"), status=None)  # type: ignore[arg-type]
    adapter = FakeSiteAdapter(
        order_pages={None: SourcePage(items=(valid, invalid), next_cursor="must-not-advance")}
    )

    with pytest.raises(IntegrityError):
        await make_engine(sessions, adapter).sync_orders()

    assert await OrderRepository(sessions).count() == 0
    checkpoint = await CheckpointRepository(sessions).get("orders")
    assert checkpoint is not None
    assert checkpoint.source_cursor is None
    assert checkpoint.failure_count == 1


@pytest.mark.asyncio
async def test_conversations_are_written_before_their_messages(
    sessions: async_sessionmaker[AsyncSession],
) -> None:
    now = datetime(2026, 9, 19, 12, 0, tzinfo=UTC)
    conversation = SourceConversation(
        source_id="conversation-1",
        buyer_reference="buyer-1",
        inquiry_subject="Question",
        unread=True,
        last_message_at=now,
        source_updated_at=now,
    )
    message = SourceMessage(
        source_id="message-1",
        conversation_source_id="conversation-1",
        direction=Direction.INBOUND,
        sender_label="buyer-1",
        content="Hello",
        attachment_metadata=(),
        source_created_at=now,
    )
    adapter = FakeSiteAdapter(
        conversation_pages={None: SourcePage(items=(conversation,), next_cursor=None)},
        message_pages={
            ("conversation-1", None): SourcePage(items=(message,), next_cursor=None)
        },
    )

    await make_engine(sessions, adapter).sync_conversations_and_messages()

    assert await ConversationRepository(sessions).count() == 1
    assert await MessageRepository(sessions).count() == 1


@pytest.mark.asyncio
async def test_full_history_persists_metadata_in_visible_source_order_and_is_idempotent(
    sessions: async_sessionmaker[AsyncSession],
) -> None:
    now = datetime(2026, 9, 19, 12, 0, tzinfo=UTC)
    conversation = SourceConversation(
        source_id="conversation-history",
        buyer_reference="buyer-history",
        inquiry_subject="Question",
        unread=False,
        last_message_at=now,
        source_updated_at=now,
    )
    messages = (
        SourceMessage(
            source_id="inquiry-1",
            conversation_source_id="conversation-history",
            direction=Direction.INBOUND,
            sender_label="buyer-history",
            content="Initial inquiry",
            attachment_metadata=({"name": "spec.pdf", "mime_type": "application/pdf"},),
            source_created_at=now,
            source_timestamp_raw="2026-09-19 20:00",
            source_sequence=1,
            source_timestamp_confidence="high",
        ),
        SourceMessage(
            source_id="chat-2",
            conversation_source_id="conversation-history",
            direction=Direction.OUTBOUND,
            sender_label="seller",
            content="Reply",
            attachment_metadata=(),
            source_created_at=now,
            source_timestamp_raw="2026-09-19 20:00",
            source_sequence=2,
            source_timestamp_confidence="medium",
        ),
    )
    adapter = FakeSiteAdapter(
        conversation_pages={
            None: SourcePage(items=(conversation,), next_cursor=None),
        },
        message_pages={
            ("conversation-history", None): SourcePage(
                items=messages, next_cursor=None, history_complete=True
            ),
        },
    )
    engine = make_engine(sessions, adapter)

    await engine.sync_conversations_and_messages()
    await engine.sync_conversations_and_messages()

    stored_conversation = await ConversationRepository(sessions).get_by_source_id(
        "conversation-history"
    )
    assert stored_conversation is not None
    stored_messages = await MessageRepository(sessions).list_for_conversation(
        stored_conversation.id
    )
    assert stored_conversation.history_complete is True
    assert [item.source_id for item in stored_messages] == ["inquiry-1", "chat-2"]
    assert [item.source_sequence for item in stored_messages] == [1, 2]
    assert stored_messages[0].source_timestamp_raw == "2026-09-19 20:00"
    assert stored_messages[0].source_timestamp_confidence == "high"
    assert stored_messages[1].direction == "outbound"
    assert stored_messages[0].attachment_metadata == [
        {"name": "spec.pdf", "mime_type": "application/pdf"}
    ]
    assert await MessageRepository(sessions).count() == 2


@pytest.mark.asyncio
async def test_incomplete_or_failed_history_never_marks_conversation_complete(
    sessions: async_sessionmaker[AsyncSession],
) -> None:
    now = datetime(2026, 9, 19, 12, 0, tzinfo=UTC)
    conversation = SourceConversation(
        source_id="conversation-incomplete",
        buyer_reference="buyer-history",
        inquiry_subject="Question",
        unread=False,
        last_message_at=now,
        source_updated_at=now,
    )
    adapter = FakeSiteAdapter(
        conversation_pages={None: SourcePage(items=(conversation,), next_cursor=None)},
        message_pages={
            ("conversation-incomplete", None): SourcePage(
                items=(), next_cursor="older-page", history_complete=False
            ),
        },
    )
    engine = make_engine(sessions, adapter)

    await engine.sync_conversations_and_messages()
    stored = await ConversationRepository(sessions).get_by_source_id(
        "conversation-incomplete"
    )
    assert stored is not None
    assert stored.history_complete is False

    adapter.message_pages[("conversation-incomplete", "older-page")] = SourcePage(
        items=(), next_cursor=None, history_complete=True
    )
    await engine.sync_conversations_and_messages()
    completed = await ConversationRepository(sessions).get_by_source_id(
        "conversation-incomplete"
    )
    assert completed is not None
    assert completed.history_complete is True

    adapter.fail_next("list_messages", ValueError("history navigation failed"))
    with pytest.raises(ValueError, match="history navigation failed"):
        await engine.sync_conversations_and_messages()

    after_failure = await ConversationRepository(sessions).get_by_source_id(
        "conversation-incomplete"
    )
    assert after_failure is not None
    assert after_failure.history_complete is True


@pytest.mark.asyncio
async def test_history_complete_marker_rolls_back_when_message_commit_fails(
    sessions: async_sessionmaker[AsyncSession],
) -> None:
    now = datetime(2026, 9, 19, 12, 0, tzinfo=UTC)
    conversation = SourceConversation(
        source_id="conversation-rollback",
        buyer_reference="buyer-history",
        inquiry_subject="Question",
        unread=False,
        last_message_at=now,
        source_updated_at=now,
    )
    invalid_message = replace(
        SourceMessage(
            source_id="message-rollback",
            conversation_source_id="conversation-rollback",
            direction=Direction.INBOUND,
            sender_label="buyer-history",
            content="valid before database binding",
            attachment_metadata=(),
            source_created_at=now,
            source_sequence=1,
        ),
        content=None,
    )
    adapter = FakeSiteAdapter(
        conversation_pages={None: SourcePage(items=(conversation,), next_cursor=None)},
        message_pages={
            ("conversation-rollback", None): SourcePage(
                items=(invalid_message,), next_cursor=None, history_complete=True
            ),
        },
    )

    with pytest.raises(IntegrityError):
        await make_engine(sessions, adapter).sync_conversations_and_messages()

    stored = await ConversationRepository(sessions).get_by_source_id("conversation-rollback")
    assert stored is not None
    assert stored.history_complete is False
    assert await MessageRepository(sessions).count() == 0


@pytest.mark.asyncio
async def test_new_conversation_update_invalidates_old_completeness_before_failed_read(
    sessions: async_sessionmaker[AsyncSession],
) -> None:
    now = datetime(2026, 9, 19, 12, 0, tzinfo=UTC)
    conversation = SourceConversation(
        source_id="conversation-updated",
        buyer_reference="buyer-history",
        inquiry_subject="Question",
        unread=False,
        last_message_at=now,
        source_updated_at=now,
    )
    message = SourceMessage(
        source_id="message-before-update",
        conversation_source_id="conversation-updated",
        direction=Direction.INBOUND,
        sender_label="buyer-history",
        content="Previously complete history",
        attachment_metadata=(),
        source_created_at=now,
        source_sequence=1,
    )
    adapter = FakeSiteAdapter(
        conversation_pages={None: SourcePage(items=(conversation,), next_cursor=None)},
        message_pages={
            ("conversation-updated", None): SourcePage(
                items=(message,), next_cursor=None, history_complete=True
            ),
        },
    )
    engine = make_engine(sessions, adapter)
    await engine.sync_conversations_and_messages()

    adapter.conversation_pages[None] = SourcePage(
        items=(
            replace(
                conversation,
                last_message_at=now + timedelta(minutes=1),
                source_updated_at=now + timedelta(minutes=1),
            ),
        ),
        next_cursor=None,
    )
    adapter.fail_next("list_messages", ValueError("history refresh failed"))
    with pytest.raises(ValueError, match="history refresh failed"):
        await engine.sync_conversations_and_messages()

    stored = await ConversationRepository(sessions).get_by_source_id("conversation-updated")
    assert stored is not None
    assert stored.history_complete is False
    assert await MessageRepository(sessions).count() == 1


@pytest.mark.asyncio
async def test_verification_required_pauses_checkpoint(
    sessions: async_sessionmaker[AsyncSession],
) -> None:
    adapter = FakeSiteAdapter()
    adapter.session_health = SessionHealth.verification_required()

    await make_engine(sessions, adapter).sync_orders()

    checkpoint = await CheckpointRepository(sessions).get("orders")
    assert checkpoint is not None
    assert checkpoint.paused_reason == "operator_action_required"
    assert adapter.order_checkpoints == []


def test_backoff_is_bounded_and_staleness_uses_utc() -> None:
    policy = BackoffPolicy(base_seconds=5, maximum_seconds=20)
    now = datetime(2026, 9, 19, 12, 0, tzinfo=UTC)

    assert [policy.next_delay(value) for value in [0, 1, 2, 3, 4]] == [5, 5, 10, 20, 20]
    assert is_stale(now - timedelta(seconds=121), now, threshold_seconds=120) is True
    assert is_stale(now - timedelta(seconds=900), now, threshold_seconds=900) is False
