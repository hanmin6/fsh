from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient, Response
from sqlalchemy import func, select

from mic_gateway.api.auth import create_api_key
from mic_gateway.config import Settings
from mic_gateway.db.base import Base, create_engine_and_sessionmaker
from mic_gateway.db.models import AuditEvent, OutboxJob
from mic_gateway.db.repositories import ConversationRepository
from mic_gateway.domain import Role, SourceConversation
from mic_gateway.main import create_app


@pytest_asyncio.fixture
async def send_api(tmp_path: Path) -> AsyncIterator[dict[str, Any]]:
    settings = Settings(
        app_data_dir=tmp_path,
        database_url=f"sqlite+aiosqlite:///{(tmp_path / 'send-api.db').as_posix()}",
    )
    engine, sessions = create_engine_and_sessionmaker(settings)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    async with sessions() as session:
        agent_key = await create_api_key(session, "agent", Role.AGENT_SEND)
        crm_key = await create_api_key(session, "crm", Role.CRM_READ)
    conversation = await ConversationRepository(sessions).upsert(
        SourceConversation(
            source_id="conversation-1",
            buyer_reference="buyer-1",
            inquiry_subject="Question",
            unread=True,
            last_message_at=datetime(2026, 9, 19, 12, 0, tzinfo=UTC),
            source_updated_at=datetime(2026, 9, 19, 12, 0, tzinfo=UTC),
            raw_snapshot={},
        )
    )
    app = create_app(settings, session_factory=sessions)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield {
            "client": client,
            "sessions": sessions,
            "agent_key": agent_key,
            "crm_key": crm_key,
            "conversation_id": conversation.id,
        }
    await engine.dispose()


async def submit(
    context: dict[str, Any],
    key: str,
    content: str,
    *,
    intent: str = "greeting",
    api_key_name: str = "agent_key",
) -> Response:
    client: AsyncClient = context["client"]
    return await client.post(
        f"/v1/conversations/{context['conversation_id']}/messages",
        headers={"X-API-Key": context[api_key_name]},
        json={
            "idempotency_key": key,
            "intent": intent,
            "content": content,
            "caller_reference": "agent-test",
        },
    )


@pytest.mark.asyncio
async def test_allowed_message_is_queued_without_touching_browser(
    send_api: dict[str, Any],
) -> None:
    response = await submit(send_api, "key-1", "Hello, thank you for contacting us.")

    assert response.status_code == 202
    assert response.json()["state"] == "queued"
    assert response.json()["intent"] == "greeting"

    async with send_api["sessions"]() as session:
        jobs = await session.scalar(select(func.count()).select_from(OutboxJob))
        audits = await session.scalar(select(func.count()).select_from(AuditEvent))
    assert jobs == 1
    assert audits == 1


@pytest.mark.asyncio
async def test_blocked_message_is_persisted_for_human_review(
    send_api: dict[str, Any],
) -> None:
    response = await submit(
        send_api,
        "key-blocked",
        "Our price is USD 12.50 each.",
        intent="non_commercial_followup",
    )

    assert response.status_code == 202
    assert response.json()["state"] == "requires_human_review"
    async with send_api["sessions"]() as session:
        audit = (await session.scalars(select(AuditEvent))).one()
    assert audit.event_type == "message_policy_decision"
    assert audit.details["code"] == "requires_human_review"
    assert "USD 12.50" not in str(audit.details)


@pytest.mark.asyncio
async def test_equivalent_retry_returns_same_job(send_api: dict[str, Any]) -> None:
    first = await submit(send_api, "same-key", "Hello")
    second = await submit(send_api, "same-key", "Hello")

    assert first.status_code == 202
    assert second.status_code == 202
    assert first.json()["id"] == second.json()["id"]
    async with send_api["sessions"]() as session:
        jobs = await session.scalar(select(func.count()).select_from(OutboxJob))
        audits = await session.scalar(select(func.count()).select_from(AuditEvent))
    assert jobs == 1
    assert audits == 2


@pytest.mark.asyncio
async def test_same_key_different_payload_returns_conflict(send_api: dict[str, Any]) -> None:
    first = await submit(send_api, "conflict-key", "Hello")
    second = await submit(send_api, "conflict-key", "Different hello")

    assert first.status_code == 202
    assert second.status_code == 409
    assert second.json()["error"]["code"] == "idempotency_conflict"


@pytest.mark.asyncio
async def test_oversized_message_and_unknown_intent_return_422(
    send_api: dict[str, Any],
) -> None:
    oversized = await submit(send_api, "key-2", "x" * 4001)
    bad_intent = await submit(send_api, "key-3", "Hello", intent="quote")

    assert oversized.status_code == 422
    assert oversized.json()["error"]["code"] == "validation_error"
    assert bad_intent.status_code == 422
    assert bad_intent.json()["error"]["code"] == "validation_error"


@pytest.mark.asyncio
async def test_crm_role_is_forbidden_before_resource_lookup(send_api: dict[str, Any]) -> None:
    response = await submit(
        send_api,
        "key-4",
        "Hello",
        api_key_name="crm_key",
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "forbidden"
