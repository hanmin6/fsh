from __future__ import annotations

import asyncio
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from mic_gateway.config import Settings
from mic_gateway.db.base import Base, create_engine_and_sessionmaker
from mic_gateway.db.repositories import (
    ConversationRepository,
    MessageRepository,
    OrderRepository,
    OutboxRepository,
)
from mic_gateway.domain import (
    Direction,
    JobState,
    MessageIntent,
    OutboxCreateRequest,
    SourceConversation,
    SourceMessage,
    SourceOrder,
    SourceOrderLine,
)
from mic_gateway.errors import ApiError


@pytest_asyncio.fixture
async def sessions(
    tmp_path: Path,
) -> async_sessionmaker[AsyncSession]:
    settings = Settings(
        app_data_dir=tmp_path,
        database_url=f"sqlite+aiosqlite:///{(tmp_path / 'repositories.db').as_posix()}",
    )
    engine, session_factory = create_engine_and_sessionmaker(settings)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    try:
        yield session_factory
    finally:
        await engine.dispose()


def make_order(source_id: str, updated_at: datetime, *, status: str = "new") -> SourceOrder:
    return SourceOrder(
        source_id=source_id,
        status=status,
        buyer_reference="buyer-1",
        currency="USD",
        total_amount=Decimal("25.00"),
        source_created_at=updated_at - timedelta(days=1),
        source_updated_at=updated_at,
        lines=(
            SourceOrderLine(
                source_line_id=f"{source_id}-line-1",
                sku="SKU-1",
                name="Widget",
                quantity=Decimal("2"),
                unit_price=Decimal("12.50"),
                raw_snapshot={},
            ),
        ),
        raw_snapshot={
            "id": source_id,
            "authorization": "Bearer secret",
            "nested": {"session_token": "secret"},
        },
    )


def make_conversation(source_id: str = "conversation-1") -> SourceConversation:
    return SourceConversation(
        source_id=source_id,
        buyer_reference="buyer-1",
        inquiry_subject="Question",
        unread=True,
        last_message_at=datetime(2026, 9, 19, 12, 0, tzinfo=UTC),
        source_updated_at=datetime(2026, 9, 19, 12, 0, tzinfo=UTC),
        raw_snapshot={},
    )


@pytest.mark.asyncio
async def test_list_refresh_preserves_buyer_identity_read_from_details(sessions):
    repository = ConversationRepository(sessions)
    source = make_conversation()
    await repository.upsert(source)
    async with sessions() as session, session.begin():
        await repository.mark_history_complete_in_session(
            session, source.source_id, buyer_id="real-buyer", buyer_name="Buyer"
        )
    refreshed = await repository.upsert(replace(source, buyer_reference="seller-contact"))
    assert refreshed.buyer_reference == "real-buyer"
    assert refreshed.raw_snapshot["buyer_id"] == "real-buyer"
    assert refreshed.raw_snapshot["buyer_name"] == "Buyer"
    assert refreshed.history_complete is True


@pytest.mark.asyncio
async def test_order_upsert_updates_without_duplication(
    sessions: async_sessionmaker[AsyncSession],
) -> None:
    repository = OrderRepository(sessions)
    source = make_order("order-1", datetime(2026, 9, 19, 12, 0, tzinfo=UTC))

    first = await repository.upsert(source)
    second = await repository.upsert(replace(source, status="shipped"))

    assert first.id == second.id
    assert second.status == "shipped"
    assert await repository.count() == 1
    assert second.raw_snapshot["authorization"] == "[REDACTED]"
    assert second.raw_snapshot["nested"]["session_token"] == "[REDACTED]"


@pytest.mark.asyncio
async def test_older_overlap_does_not_replace_newer_order(
    sessions: async_sessionmaker[AsyncSession],
) -> None:
    repository = OrderRepository(sessions)
    newer = make_order("order-1", datetime(2026, 9, 19, 12, 0, tzinfo=UTC), status="paid")
    older = make_order("order-1", datetime(2026, 9, 19, 11, 0, tzinfo=UTC), status="new")

    await repository.upsert(newer)
    result = await repository.upsert(older)

    assert result.status == "paid"
    assert result.source_updated_at == newer.source_updated_at


@pytest.mark.asyncio
async def test_order_seek_pagination_is_stable(
    sessions: async_sessionmaker[AsyncSession],
) -> None:
    repository = OrderRepository(sessions)
    start = datetime(2026, 9, 19, 12, 0, tzinfo=UTC)
    for index in range(3):
        await repository.upsert(make_order(f"order-{index}", start - timedelta(hours=index)))

    first, cursor = await repository.list_page(limit=2)
    second, final_cursor = await repository.list_page(limit=2, cursor=cursor)

    assert [row.source_id for row in first] == ["order-0", "order-1"]
    assert [row.source_id for row in second] == ["order-2"]
    assert final_cursor is None


@pytest.mark.asyncio
async def test_message_without_source_id_deduplicates_by_fingerprint(
    sessions: async_sessionmaker[AsyncSession],
) -> None:
    conversations = ConversationRepository(sessions)
    messages = MessageRepository(sessions)
    await conversations.upsert(make_conversation())
    source = SourceMessage(
        source_id=None,
        conversation_source_id="conversation-1",
        direction=Direction.INBOUND,
        sender_label="buyer-1",
        content="Hello",
        attachment_metadata=(),
        source_created_at=datetime(2026, 9, 19, 12, 1, tzinfo=UTC),
        raw_snapshot={},
    )

    first = await messages.upsert(source)
    second = await messages.upsert(source)

    assert first.id == second.id
    assert await messages.count() == 1


@pytest.mark.asyncio
async def test_concurrent_same_idempotency_key_creates_one_job(
    sessions: async_sessionmaker[AsyncSession],
) -> None:
    conversations = ConversationRepository(sessions)
    conversation = await conversations.upsert(make_conversation())
    repository = OutboxRepository(sessions)
    request = OutboxCreateRequest(
        idempotency_key="same-key",
        payload_digest="a" * 64,
        conversation_id=conversation.id,
        intent=MessageIntent.GREETING,
        content="Hello",
        caller_reference=None,
        caller_key_id=None,
        request_id="request-1",
        initial_state=JobState.QUEUED,
    )

    results = await asyncio.gather(
        repository.create_idempotent(request),
        repository.create_idempotent(request),
    )

    assert results[0].job.id == results[1].job.id
    assert await repository.count() == 1


@pytest.mark.asyncio
async def test_reusing_idempotency_key_with_different_payload_conflicts(
    sessions: async_sessionmaker[AsyncSession],
) -> None:
    conversations = ConversationRepository(sessions)
    conversation = await conversations.upsert(make_conversation())
    repository = OutboxRepository(sessions)
    request = OutboxCreateRequest(
        idempotency_key="same-key",
        payload_digest="a" * 64,
        conversation_id=conversation.id,
        intent=MessageIntent.GREETING,
        content="Hello",
        caller_reference=None,
        caller_key_id=None,
        request_id="request-1",
    )
    await repository.create_idempotent(request)

    with pytest.raises(ApiError) as exc:
        await repository.create_idempotent(replace(request, payload_digest="b" * 64))

    assert exc.value.status_code == 409
    assert exc.value.code == "idempotency_conflict"


@pytest.mark.asyncio
async def test_conversation_history_completion_records_buyer_name_and_country(
    sessions: async_sessionmaker[AsyncSession],
) -> None:
    conversations = ConversationRepository(sessions)
    created = await conversations.upsert(make_conversation())
    assert created.history_complete is False
    assert created.buyer_name is None
    assert created.country is None

    async with sessions() as session, session.begin():
        await conversations.mark_history_complete_in_session(
            session,
            created.source_id,
            buyer_name="Global Trade Ltd",
            country="France",
        )

    updated = await conversations.get(created.id)
    assert updated is not None
    assert updated.history_complete is True
    assert updated.buyer_name == "Global Trade Ltd"
    assert updated.country == "France"

    # Subsequent upsert from conversation list retains buyer_name and country
    re_synced = await conversations.upsert(make_conversation())
    assert re_synced.buyer_name == "Global Trade Ltd"
    assert re_synced.country == "France"
