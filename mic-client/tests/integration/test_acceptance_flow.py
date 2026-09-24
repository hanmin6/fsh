from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any
from uuid import UUID

import httpx
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from mic_gateway.adapters.base import SendAttempt, SessionHealth, SourcePage
from mic_gateway.adapters.fake import FakeSiteAdapter
from mic_gateway.api.auth import create_api_key
from mic_gateway.config import Settings
from mic_gateway.db.base import Base, create_engine_and_sessionmaker
from mic_gateway.db.repositories import (
    CheckpointRepository,
    ConversationRepository,
    MessageRepository,
    OrderRepository,
    OutboxRepository,
)
from mic_gateway.domain import (
    Direction,
    Role,
    SourceConversation,
    SourceMessage,
    SourceOrder,
    SourceOrderLine,
)
from mic_gateway.main import create_app
from mic_gateway.messaging.outbox import OutboxWorker
from mic_gateway.sync.engine import SyncEngine

NOW = datetime(2026, 9, 19, 12, 0, tzinfo=UTC)


@dataclass(slots=True)
class AcceptanceGateway:
    engine: AsyncEngine
    sessions: async_sessionmaker[AsyncSession]
    adapter: FakeSiteAdapter
    sync: SyncEngine
    outbox: OutboxWorker
    app: Any
    keys: dict[Role, str]

    def client(self, role: Role) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            transport=httpx.ASGITransport(app=self.app),
            base_url="http://test",
            headers={"X-API-Key": self.keys[role]},
        )


def source_order() -> SourceOrder:
    return SourceOrder(
        source_id="order-1",
        status="pending",
        buyer_reference="buyer-1",
        currency="USD",
        total_amount=Decimal("25.00"),
        source_created_at=NOW,
        source_updated_at=NOW,
        lines=(
            SourceOrderLine(
                source_line_id="line-1",
                sku="SKU-1",
                name="Sample product",
                quantity=Decimal("2"),
                unit_price=Decimal("12.50"),
            ),
        ),
    )


def source_conversation() -> SourceConversation:
    return SourceConversation(
        source_id="conversation-1",
        buyer_reference="buyer-1",
        inquiry_subject="Product question",
        unread=True,
        last_message_at=NOW,
        source_updated_at=NOW,
    )


def source_message() -> SourceMessage:
    return SourceMessage(
        source_id="message-1",
        conversation_source_id="conversation-1",
        direction=Direction.INBOUND,
        sender_label="buyer",
        content="Hello",
        attachment_metadata=(),
        source_created_at=NOW,
    )


@pytest_asyncio.fixture
async def gateway(tmp_path: Path) -> Any:
    settings = Settings(
        app_data_dir=tmp_path,
        database_url=f"sqlite+aiosqlite:///{(tmp_path / 'acceptance.db').as_posix()}",
    )
    engine, sessions = create_engine_and_sessionmaker(settings)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    adapter = FakeSiteAdapter(
        order_pages={None: SourcePage(items=(source_order(),), next_cursor=None)},
        conversation_pages={
            None: SourcePage(items=(source_conversation(),), next_cursor=None)
        },
        message_pages={
            ("conversation-1", None): SourcePage(
                items=(source_message(),), next_cursor=None
            )
        },
    )
    orders = OrderRepository(sessions)
    conversations = ConversationRepository(sessions)
    messages = MessageRepository(sessions)
    checkpoints = CheckpointRepository(sessions)
    jobs = OutboxRepository(sessions)
    sync = SyncEngine(
        adapter=adapter,
        sessions=sessions,
        orders=orders,
        conversations=conversations,
        messages=messages,
        checkpoints=checkpoints,
    )
    outbox = OutboxWorker(
        jobs=jobs,
        adapter=adapter,
        runtime=object(),  # type: ignore[arg-type]
        sleeper=lambda _: asyncio.sleep(0),
    )
    app = create_app(
        settings,
        session_factory=sessions,
        outbox_worker=outbox,
    )
    keys: dict[Role, str] = {}
    async with sessions() as session:
        for role in Role:
            keys[role] = await create_api_key(session, f"acceptance-{role.value}", role)
    harness = AcceptanceGateway(
        engine=engine,
        sessions=sessions,
        adapter=adapter,
        sync=sync,
        outbox=outbox,
        app=app,
        keys=keys,
    )
    try:
        yield harness
    finally:
        await engine.dispose()


async def submit_greeting(
    client: httpx.AsyncClient,
    conversation_id: str,
    *,
    idempotency_key: str,
    content: str = "Hello, thank you for contacting us.",
) -> httpx.Response:
    return await client.post(
        f"/v1/conversations/{conversation_id}/messages",
        json={
            "idempotency_key": idempotency_key,
            "intent": "greeting",
            "content": content,
            "caller_reference": "acceptance",
        },
    )


@pytest.mark.asyncio
async def test_crm_sync_and_agent_send_acceptance(gateway: AcceptanceGateway) -> None:
    await gateway.sync.sync_orders()
    await gateway.sync.sync_conversations_and_messages()
    gateway.adapter.next_send = SendAttempt.sent("outbound-1")

    async with gateway.client(Role.CRM_READ) as crm, gateway.client(Role.AGENT_SEND) as agent:
        orders = await crm.get("/v1/orders")
        conversations = await crm.get("/v1/conversations")
        conversation_id = conversations.json()["items"][0]["id"]
        messages = await crm.get(f"/v1/conversations/{conversation_id}/messages")
        job = await submit_greeting(
            agent,
            conversation_id,
            idempotency_key="acceptance-1",
        )
        await gateway.outbox.run_once()
        final = await agent.get(f"/v1/jobs/{job.json()['id']}")

    assert orders.status_code == 200
    assert orders.json()["items"][0]["source_id"] == "order-1"
    assert messages.json()["items"][0]["content"] == "Hello"
    assert job.status_code == 202
    assert final.json()["state"] == "sent"


@pytest.mark.asyncio
async def test_permissions_policy_and_concurrent_idempotency(
    gateway: AcceptanceGateway,
) -> None:
    await gateway.sync.sync_conversations_and_messages()
    async with gateway.client(Role.CRM_READ) as crm, gateway.client(Role.AGENT_SEND) as agent:
        conversations = await crm.get("/v1/conversations")
        conversation_id = conversations.json()["items"][0]["id"]

        forbidden = await submit_greeting(
            crm,
            conversation_id,
            idempotency_key="crm-cannot-send",
        )
        quote = await submit_greeting(
            agent,
            conversation_id,
            idempotency_key="quote-human",
            content="Please quote USD 100 for this order.",
        )
        first, second = await asyncio.gather(
            submit_greeting(
                agent,
                conversation_id,
                idempotency_key="same-event",
            ),
            submit_greeting(
                agent,
                conversation_id,
                idempotency_key="same-event",
            ),
        )

    assert forbidden.status_code == 403
    assert quote.status_code == 202
    assert quote.json()["state"] == "requires_human_review"
    assert first.status_code == second.status_code == 202
    assert first.json()["id"] == second.json()["id"]


@pytest.mark.asyncio
async def test_login_loss_pauses_sync(gateway: AcceptanceGateway) -> None:
    gateway.adapter.session_health = SessionHealth.authentication_required()

    synced = await gateway.sync.sync_orders()
    checkpoint = await CheckpointRepository(gateway.sessions).get("orders")

    assert synced == 0
    assert checkpoint is not None
    assert checkpoint.paused_reason == "operator_action_required"
    assert gateway.adapter.order_checkpoints == []


@pytest.mark.asyncio
async def test_uncertain_send_is_not_retried(gateway: AcceptanceGateway) -> None:
    await gateway.sync.sync_conversations_and_messages()
    gateway.adapter.next_send = SendAttempt.uncertain("confirmation_missing")
    async with gateway.client(Role.AGENT_SEND) as agent:
        conversations = await agent.get("/v1/conversations")
        conversation_id = conversations.json()["items"][0]["id"]
        job = await submit_greeting(
            agent,
            conversation_id,
            idempotency_key="uncertain-event",
        )

    await gateway.outbox.run_once()
    await gateway.outbox.run_once()
    stored = await OutboxRepository(gateway.sessions).get(UUID(job.json()["id"]))

    assert stored is not None
    assert stored.state == "uncertain"
    assert gateway.adapter.send_calls == [
        ("conversation-1", "Hello, thank you for contacting us.")
    ]


@pytest.mark.asyncio
async def test_restart_recovers_sending_as_uncertain(
    gateway: AcceptanceGateway,
) -> None:
    await gateway.sync.sync_conversations_and_messages()
    async with gateway.client(Role.AGENT_SEND) as agent:
        conversations = await agent.get("/v1/conversations")
        conversation_id = conversations.json()["items"][0]["id"]
        job = await submit_greeting(
            agent,
            conversation_id,
            idempotency_key="restart-event",
        )

    jobs = OutboxRepository(gateway.sessions)
    claimed = await jobs.claim_next(NOW)
    assert claimed is not None and claimed.state == "sending"

    restarted = OutboxWorker(
        jobs=jobs,
        adapter=gateway.adapter,
        runtime=object(),  # type: ignore[arg-type]
        sleeper=lambda _: asyncio.sleep(0),
    )
    recovered = await restarted.recover_after_restart()
    stored = await jobs.get(UUID(job.json()["id"]))

    assert recovered == 1
    assert stored is not None
    assert stored.state == "uncertain"
