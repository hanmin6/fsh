from __future__ import annotations

import asyncio
from typing import Any, cast

import pytest

from mic_gateway.adapters.base import SessionHealth
from mic_gateway.adapters.fake import FakeSiteAdapter
from mic_gateway.runtime.scheduler import GatewayScheduler


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
