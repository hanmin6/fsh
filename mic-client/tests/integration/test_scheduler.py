from __future__ import annotations

import asyncio
from typing import Any, cast
from unittest.mock import AsyncMock, MagicMock

import pytest

from mic_gateway.adapters.base import SessionHealth
from mic_gateway.adapters.fake import FakeSiteAdapter
from mic_gateway.runtime.scheduler import GatewayScheduler
from mic_gateway.browser.runtime import BrowserSessionState


class SyncStub:
    def __init__(self) -> None:
        self.orders = 0
        self.conversations = 0

    async def sync_orders(self) -> int:
        self.orders += 1
        return 0

    async def sync_conversations_and_messages(self) -> int:
        self.conversations += 1
        return 0


class WorkerStub:
    def __init__(self) -> None:
        self.runs = 0

    async def run_once(self) -> None:
        self.runs += 1


class StatusStub:
    def __init__(self) -> None:
        self.health: SessionHealth | None = None

    def set_session_health(self, health: SessionHealth) -> None:
        self.health = health


@pytest.mark.asyncio
async def test_stalled_read_times_out_and_releases_lock_for_health_probe():
    cancelled = asyncio.Event()
    class HungSync(SyncStub):
        async def sync_conversations_and_messages(self):
            try:
                await asyncio.Event().wait()
            finally:
                cancelled.set()
    scheduler = GatewayScheduler(adapter=FakeSiteAdapter(), sync_engine=HungSync(),
                                 outbox_worker=WorkerStub(), status_service=StatusStub())
    scheduler._operation_timeouts['conversations'] = 0.01
    await scheduler._run('health')
    with pytest.raises(TimeoutError):
        await scheduler._run('conversations')
    assert cancelled.is_set()
    assert not scheduler._lock.locked()
    await asyncio.wait_for(scheduler._run('health'), timeout=1)


@pytest.mark.asyncio
async def test_verification_challenge_pauses_all_work() -> None:
    adapter = FakeSiteAdapter()
    adapter.session_health = SessionHealth.verification_required()
    sync = SyncStub()
    worker = WorkerStub()
    status = StatusStub()
    scheduler = GatewayScheduler(
        adapter=adapter,
        sync_engine=cast(Any, sync),
        outbox_worker=cast(Any, worker),
        status_service=cast(Any, status),
    )

    await scheduler.tick()

    assert status.health is not None and status.health.requires_operator
    assert sync.orders == 0 and sync.conversations == 0 and worker.runs == 0


@pytest.mark.asyncio
async def test_start_and_stop_use_independent_interruptible_loops() -> None:
    adapter = FakeSiteAdapter()
    sync = SyncStub()
    worker = WorkerStub()
    scheduler = GatewayScheduler(
        adapter=adapter,
        sync_engine=cast(Any, sync),
        outbox_worker=cast(Any, worker),
        status_service=cast(Any, StatusStub()),
        conversation_interval=0.01,
        order_interval=0.01,
        outbox_interval=0.01,
        health_interval=0.01,
    )

    await scheduler.start()
    await asyncio.sleep(0.04)
    await scheduler.stop()

    assert sync.orders > 0
    assert sync.conversations > 0
    assert worker.runs > 0


@pytest.mark.asyncio
async def test_paused_outbound_does_not_stop_inbound_reads(monkeypatch: Any) -> None:
    monkeypatch.setenv("FUSANHE_OUTBOUND_PAUSED", "true")
    sync, worker = SyncStub(), WorkerStub()
    scheduler = GatewayScheduler(
        adapter=FakeSiteAdapter(), sync_engine=cast(Any, sync),
        outbox_worker=cast(Any, worker), status_service=cast(Any, StatusStub()),
    )
    await scheduler.tick()
    assert sync.conversations == 1 and sync.orders == 1
    assert worker.runs == 0


@pytest.mark.asyncio
async def test_manual_sync_waits_for_login_and_deduplicates() -> None:
    adapter = FakeSiteAdapter()
    adapter.session_health = SessionHealth.authentication_required()
    sync = SyncStub()
    scheduler = GatewayScheduler(
        adapter=adapter, sync_engine=cast(Any, sync),
        outbox_worker=cast(Any, WorkerStub()), status_service=cast(Any, StatusStub()),
    )
    assert scheduler.queue_manual_sync("conversations") is True
    assert scheduler.queue_manual_sync("conversations") is False
    await scheduler.tick()
    assert sync.conversations == 0
    assert scheduler.queue_manual_sync("conversations") is False
    adapter.session_health = SessionHealth.available()
    await scheduler.tick()
    assert sync.conversations == 1
    assert scheduler.queue_manual_sync("conversations") is True


@pytest.mark.asyncio
async def test_stopped_browser_is_recovered_before_source_reads() -> None:
    runtime = MagicMock()
    runtime.session_state = BrowserSessionState.STOPPED
    runtime.stop = AsyncMock()
    runtime.start = AsyncMock()
    sync = SyncStub()
    scheduler = GatewayScheduler(
        adapter=FakeSiteAdapter(), sync_engine=cast(Any, sync),
        outbox_worker=cast(Any, WorkerStub()), status_service=cast(Any, StatusStub()),
        browser_runtime=runtime,
    )
    await scheduler.tick()
    runtime.stop.assert_awaited_once()
    runtime.start.assert_awaited_once()
    assert sync.conversations == 1
