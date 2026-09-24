from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from mic_gateway.api.auth import create_api_key
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
    MessageIntent,
    OutboxCreateRequest,
    Role,
    SourceConversation,
    SourceMessage,
    SourceOrder,
    SourceOrderLine,
)
from mic_gateway.main import create_app


@pytest_asyncio.fixture
async def read_api(tmp_path: Path) -> AsyncIterator[dict[str, Any]]:
    settings = Settings(
        app_data_dir=tmp_path,
        database_url=f"sqlite+aiosqlite:///{(tmp_path / 'read-api.db').as_posix()}",
    )
    engine, sessions = create_engine_and_sessionmaker(settings)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    async with sessions() as session:
        api_key = await create_api_key(session, "crm", Role.CRM_READ)

    orders = OrderRepository(sessions)
    conversations = ConversationRepository(sessions)
    messages = MessageRepository(sessions)
    outbox = OutboxRepository(sessions)
    start = datetime(2026, 9, 19, 12, 0, tzinfo=UTC)
    for index in range(3):
        await orders.upsert(
            SourceOrder(
                source_id=f"order-{index}",
                status="paid" if index != 2 else "new",
                buyer_reference="buyer-1",
                currency="USD",
                total_amount=Decimal("25.00"),
                source_created_at=start - timedelta(days=1, hours=index),
                source_updated_at=start - timedelta(hours=index),
                lines=(
                    SourceOrderLine(
                        source_line_id=f"line-{index}",
                        sku=f"SKU-{index}",
                        name="Widget",
                        quantity=Decimal("2"),
                        unit_price=Decimal("12.50"),
                        raw_snapshot={"cookie": "secret"},
                    ),
                ),
                raw_snapshot={"authorization": "secret"},
            )
        )

    conversation = await conversations.upsert(
        SourceConversation(
            source_id="conversation-1",
            buyer_reference="buyer-1",
            inquiry_subject="Question",
            unread=True,
            last_message_at=start + timedelta(minutes=2),
            source_updated_at=start + timedelta(minutes=2),
            raw_snapshot={"session_token": "secret"},
        )
    )
    async with sessions() as session, session.begin():
        stored_conversation = await session.get(type(conversation), conversation.id)
        assert stored_conversation is not None
        stored_conversation.history_complete = True
        stored_conversation.raw_snapshot = {
            "session_token": "secret",
            "buyer_name": "Test Buyer",
            "country": "Canada",
        }
    for index, content in [(1, "First"), (2, "Second")]:
        await messages.upsert(
            SourceMessage(
                source_id=f"message-{index}",
                conversation_source_id="conversation-1",
                direction=Direction.INBOUND,
                sender_label="buyer-1",
                content=content,
                attachment_metadata=(),
                source_created_at=start + timedelta(minutes=1),
                source_sequence=index,
                source_timestamp_raw=f"2026-09-19 20:0{index}",
                source_timestamp_confidence="high",
                raw_snapshot={"token": "secret"},
            )
        )
    job = (
        await outbox.create_idempotent(
            OutboxCreateRequest(
                idempotency_key="read-api-job",
                payload_digest="a" * 64,
                conversation_id=conversation.id,
                intent=MessageIntent.GREETING,
                content="Hello",
                caller_reference="crm-test",
                caller_key_id=None,
                request_id="request-1",
            )
        )
    ).job

    app = create_app(settings, session_factory=sessions)
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers={"X-API-Key": api_key},
    ) as client:
        yield {
            "app": app,
            "client": client,
            "conversation_id": conversation.id,
            "job_id": job.id,
        }
    await engine.dispose()


@pytest.mark.asyncio
async def test_orders_return_deterministic_cursor_pages_without_raw_data(
    read_api: dict[str, Any],
) -> None:
    client: AsyncClient = read_api["client"]
    first = await client.get("/v1/orders", params={"limit": 2})
    assert first.status_code == 200
    assert first.json()["next_cursor"]
    second = await client.get(
        "/v1/orders", params={"limit": 2, "cursor": first.json()["next_cursor"]}
    )

    payloads = first.json()["items"] + second.json()["items"]
    ids = [item["id"] for item in payloads]
    assert len(ids) == 3
    assert ids == list(dict.fromkeys(ids))
    assert second.json()["next_cursor"] is None
    assert payloads[0]["lines"][0]["sku"] == "SKU-0"
    assert "raw_snapshot" not in str(payloads)
    assert "secret" not in str(payloads)


@pytest.mark.asyncio
async def test_order_filters_and_detail_not_found(read_api: dict[str, Any]) -> None:
    client: AsyncClient = read_api["client"]
    filtered = await client.get("/v1/orders", params={"status": "new", "buyer": "buyer-1"})
    missing = await client.get("/v1/orders/00000000-0000-0000-0000-000000000000")

    assert [item["source_id"] for item in filtered.json()["items"]] == ["order-2"]
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "resource_not_found"


@pytest.mark.asyncio
async def test_invalid_updated_after_and_limits_use_safe_validation_error(
    read_api: dict[str, Any],
) -> None:
    client: AsyncClient = read_api["client"]
    invalid_time = await client.get("/v1/orders", params={"updated_after": "yesterday"})
    invalid_limit = await client.get("/v1/orders", params={"limit": 201})

    assert invalid_time.status_code == 422
    assert invalid_time.json()["error"]["code"] == "validation_error"
    assert invalid_limit.status_code == 422
    assert invalid_limit.json()["error"]["code"] == "validation_error"


@pytest.mark.asyncio
async def test_conversations_messages_and_jobs_are_normalized(read_api: dict[str, Any]) -> None:
    client: AsyncClient = read_api["client"]
    conversations = await client.get("/v1/conversations", params={"unread": True})
    messages = await client.get(
        f"/v1/conversations/{read_api['conversation_id']}/messages"
    )
    job = await client.get(f"/v1/jobs/{read_api['job_id']}")

    assert conversations.status_code == 200
    assert conversations.json()["items"][0]["source_id"] == "conversation-1"
    assert conversations.json()["items"][0]["history_complete"] is True
    assert conversations.json()["items"][0]["buyer_name"] == "Test Buyer"
    assert conversations.json()["items"][0]["country"] == "Canada"
    assert [item["content"] for item in messages.json()["items"]] == ["First", "Second"]
    assert [item["source_sequence"] for item in messages.json()["items"]] == [1, 2]
    assert messages.json()["items"][0]["source_timestamp_raw"] == "2026-09-19 20:01"
    assert messages.json()["items"][0]["source_timestamp_confidence"] == "high"
    assert messages.json()["next_cursor"] is None
    assert job.json()["state"] == "queued"
    assert job.json()["intent"] == "greeting"
    assert "payload_digest" not in job.text
    assert "idempotency_key" not in job.text


@pytest.mark.asyncio
async def test_message_cursor_pages_follow_source_sequence_when_timestamps_tie(
    read_api: dict[str, Any],
) -> None:
    client: AsyncClient = read_api["client"]
    first = await client.get(
        f"/v1/conversations/{read_api['conversation_id']}/messages", params={"limit": 1}
    )
    second = await client.get(
        f"/v1/conversations/{read_api['conversation_id']}/messages",
        params={"limit": 1, "cursor": first.json()["next_cursor"]},
    )

    assert first.status_code == second.status_code == 200
    assert first.json()["items"][0]["source_sequence"] == 1
    assert second.json()["items"][0]["source_sequence"] == 2
    assert second.json()["next_cursor"] is None


def test_openapi_documents_read_contract(read_api: dict[str, Any]) -> None:
    schema = read_api["app"].openapi()

    assert "/v1/orders" in schema["paths"]
    parameters = schema["paths"]["/v1/orders"]["get"]["parameters"]
    assert any(item["name"] == "X-API-Key" and item["in"] == "header" for item in parameters)
    assert any(item["name"] == "cursor" for item in parameters)
    assert schema["components"]["schemas"]["MessageIntent"]["enum"] == [
        "greeting",
        "acknowledgement",
        "holiday_wish",
        "non_commercial_followup",
    ]
    assert schema["components"]["schemas"]["JobState"]["enum"] == [
        "queued",
        "sending",
        "sent",
        "requires_human_review",
        "failed",
        "uncertain",
    ]
