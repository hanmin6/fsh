from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from mic_gateway.adapters.base import SendAttempt
from mic_gateway.adapters.fake import FakeSiteAdapter
from mic_gateway.browser.runtime import BrowserRuntimeCrashed
from mic_gateway.config import Settings
from mic_gateway.db.base import Base, create_engine_and_sessionmaker
from mic_gateway.db.repositories import ConversationRepository, OutboxRepository
from mic_gateway.domain import (
    Direction,
    JobState,
    MessageIntent,
    OutboxCreateRequest,
    SourceConversation,
    SourceMessage,
)
from mic_gateway.messaging.outbox import OutboxWorker


class DirectRuntime:
    async def run_serialized[T](self, operation: Callable[[object], Awaitable[T]]) -> T:
        del operation
        raise AssertionError("the adapter owns browser serialization")


class ManualTime:
    def __init__(self) -> None:
        self.now = datetime(2026, 9, 19, 12, 0, tzinfo=UTC)
        self.monotonic_value = 100.0
        self.sleeps: list[float] = []

    def utcnow(self) -> datetime:
        return self.now

    def monotonic(self) -> float:
        return self.monotonic_value

    async def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.monotonic_value += seconds


@pytest_asyncio.fixture
async def outbox_context(tmp_path: Path) -> Any:
    settings = Settings(
        app_data_dir=tmp_path,
        database_url=f"sqlite+aiosqlite:///{(tmp_path / 'outbox.db').as_posix()}",
    )
    engine, sessions = create_engine_and_sessionmaker(settings)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    conversation = await ConversationRepository(sessions).upsert(
        SourceConversation(
            source_id="conversation-1",
            buyer_reference="buyer-1",
            inquiry_subject="Question",
            unread=True,
            last_message_at=datetime(2026, 9, 19, 12, 0, tzinfo=UTC),
            source_updated_at=datetime(2026, 9, 19, 12, 0, tzinfo=UTC),
        )
    )
    try:
        yield sessions, conversation
    finally:
        await engine.dispose()


async def create_job(
    sessions: async_sessionmaker[AsyncSession],
    conversation_id: Any,
    key: str,
) -> Any:
    return (
        await OutboxRepository(sessions).create_idempotent(
            OutboxCreateRequest(
                idempotency_key=key,
                payload_digest=(key.encode().hex() + "0" * 64)[:64],
                conversation_id=conversation_id,
                intent=MessageIntent.GREETING,
                content=f"Hello {key}",
                caller_reference="test",
                caller_key_id=None,
                request_id=f"request-{key}",
            )
        )
    ).job


def make_worker(
    sessions: async_sessionmaker[AsyncSession],
    adapter: FakeSiteAdapter,
    manual_time: ManualTime | None = None,
) -> OutboxWorker:
    time = manual_time or ManualTime()
    return OutboxWorker(
        jobs=OutboxRepository(sessions),
        adapter=adapter,
        runtime=DirectRuntime(),  # type: ignore[arg-type]
        clock=time.utcnow,
        monotonic=time.monotonic,
        sleeper=time.sleep,
    )


@pytest.mark.asyncio
async def test_confirmed_send_becomes_sent(outbox_context: Any) -> None:
    sessions, conversation = outbox_context
    job = await create_job(sessions, conversation.id, "sent")
    adapter = FakeSiteAdapter()
    adapter.next_send = SendAttempt.sent("source-message-1")

    result = await make_worker(sessions, adapter).run_once()

    stored = await OutboxRepository(sessions).get(job.id)
    assert result is not None
    assert stored is not None
    assert stored.state == JobState.SENT
    assert stored.sent_at is not None
    assert stored.safe_result_metadata["source_message_id"] == "source-message-1"


@pytest.mark.asyncio
async def test_uncertain_send_is_not_automatically_retried(outbox_context: Any) -> None:
    sessions, conversation = outbox_context
    job = await create_job(sessions, conversation.id, "uncertain")
    adapter = FakeSiteAdapter()
    adapter.next_send = SendAttempt.uncertain("confirmation_missing")
    worker = make_worker(sessions, adapter)

    await worker.run_once()
    await worker.run_once()

    stored = await OutboxRepository(sessions).get(job.id)
    assert adapter.send_calls == [("conversation-1", "Hello uncertain")]
    assert stored is not None
    assert stored.state == JobState.UNCERTAIN


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("error", "expected_code"),
    [
        (BrowserRuntimeCrashed("browser closed"), "browser_runtime_crashed"),
        (RuntimeError("unexpected adapter failure"), "unclassified_send_error"),
    ],
)
async def test_send_exceptions_become_uncertain_without_retry(
    outbox_context: Any, error: Exception, expected_code: str
) -> None:
    sessions, conversation = outbox_context
    job = await create_job(sessions, conversation.id, f"exception-{expected_code}")
    adapter = FakeSiteAdapter()
    adapter.fail_next("send_message", error)

    await make_worker(sessions, adapter).run_once()
    await make_worker(sessions, adapter).run_once()

    stored = await OutboxRepository(sessions).get(job.id)
    assert stored is not None
    assert stored.state == JobState.UNCERTAIN
    assert stored.failure_code == expected_code
    assert len(adapter.send_calls) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("attempt", "expected"),
    [
        (SendAttempt.transient_failure("network_timeout"), JobState.QUEUED),
        (SendAttempt.permanent_failure("recipient_closed"), JobState.FAILED),
    ],
)
async def test_explicit_failures_have_bounded_states(
    outbox_context: Any, attempt: SendAttempt, expected: JobState
) -> None:
    sessions, conversation = outbox_context
    job = await create_job(sessions, conversation.id, f"failure-{expected.value}")
    adapter = FakeSiteAdapter()
    adapter.next_send = attempt

    await make_worker(sessions, adapter).run_once()

    stored = await OutboxRepository(sessions).get(job.id)
    assert stored is not None
    assert stored.state == expected
    assert stored.attempt_count == 1
    if expected is JobState.QUEUED:
        assert stored.next_attempt_at is not None


@pytest.mark.asyncio
async def test_reconciliation_marks_matching_message_sent_without_resend(
    outbox_context: Any,
) -> None:
    sessions, conversation = outbox_context
    job = await create_job(sessions, conversation.id, "reconcile")
    adapter = FakeSiteAdapter()
    adapter.next_send = SendAttempt.uncertain("confirmation_missing")
    worker = make_worker(sessions, adapter)
    await worker.run_once()
    adapter.send_calls.clear()
    adapter.outbound_match = SourceMessage(
        source_id="source-message-1",
        conversation_source_id="conversation-1",
        direction=Direction.OUTBOUND,
        sender_label="seller",
        content="Hello reconcile",
        attachment_metadata=(),
        source_created_at=datetime(2026, 9, 19, 12, 1, tzinfo=UTC),
    )

    await worker.reconcile_uncertain(job.id)

    stored = await OutboxRepository(sessions).get(job.id)
    assert adapter.send_calls == []
    assert stored is not None
    assert stored.state == JobState.SENT
    assert len(adapter.match_calls) == 1


@pytest.mark.asyncio
async def test_restart_moves_abandoned_sending_to_uncertain(outbox_context: Any) -> None:
    sessions, conversation = outbox_context
    job = await create_job(sessions, conversation.id, "restart")
    claimed = await OutboxRepository(sessions).claim_next(
        datetime(2026, 9, 19, 12, 0, tzinfo=UTC)
    )
    assert claimed is not None

    recovered = await make_worker(sessions, FakeSiteAdapter()).recover_after_restart()

    stored = await OutboxRepository(sessions).get(job.id)
    assert recovered == 1
    assert stored is not None
    assert stored.state == JobState.UNCERTAIN


@pytest.mark.asyncio
async def test_claim_is_atomic_across_competing_workers(outbox_context: Any) -> None:
    sessions, conversation = outbox_context
    await create_job(sessions, conversation.id, "atomic")
    repository = OutboxRepository(sessions)
    now = datetime(2026, 9, 19, 12, 0, tzinfo=UTC)

    claims = await asyncio.gather(repository.claim_next(now), repository.claim_next(now))

    assert sum(claim is not None for claim in claims) == 1


@pytest.mark.asyncio
async def test_website_sends_are_spaced_by_at_least_ten_seconds(
    outbox_context: Any,
) -> None:
    sessions, conversation = outbox_context
    await create_job(sessions, conversation.id, "first")
    await create_job(sessions, conversation.id, "second")
    manual_time = ManualTime()
    worker = make_worker(sessions, FakeSiteAdapter(), manual_time)

    await worker.run_once()
    await worker.run_once()

    assert manual_time.sleeps == [10.0]
