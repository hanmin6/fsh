from __future__ import annotations

import asyncio
import logging
import os
from collections.abc import Awaitable, Callable
from typing import Any

from mic_gateway.adapters.base import SessionHealth, SiteAdapter
from mic_gateway.browser.runtime import BrowserRuntime, BrowserSessionState
from mic_gateway.sync.engine import safe_failure_code

logger = logging.getLogger(__name__)


class GatewayScheduler:
    """Interruptible polling with serialized browser work and login gating."""

    def __init__(
        self,
        *,
        adapter: SiteAdapter,
        sync_engine: Any,
        outbox_worker: Any,
        status_service: Any,
        browser_runtime: BrowserRuntime | None = None,
        conversation_interval: float = 30,
        order_interval: float = 300,
        outbox_interval: float = 1,
        health_interval: float = 10,
    ) -> None:
        self.adapter = adapter
        self.sync_engine = sync_engine
        self.outbox_worker = outbox_worker
        self.status_service = status_service
        self.browser_runtime = browser_runtime
        self._health = SessionHealth.unavailable("not_checked")
        self._lock = asyncio.Lock()
        self._tasks: list[asyncio.Task[None]] = []
        self._manual: set[str] = set()
        self._wake = {name: asyncio.Event() for name in ("orders", "conversations")}
        self._intervals = {
            "health": health_interval,
            "conversations": conversation_interval,
            "orders": order_interval,
            "outbox": outbox_interval,
        }
        if any(value <= 0 for value in self._intervals.values()):
            raise ValueError("Polling intervals must be positive")

    def queue_manual_sync(self, resource: str) -> bool:
        if resource not in self._wake:
            raise ValueError("Unknown sync resource")
        if resource in self._manual:
            return False
        self._manual.add(resource)
        self._wake[resource].set()
        return True

    async def _probe(self) -> None:
        try:
            if self.browser_runtime is not None and (
                self.browser_runtime.session_state is BrowserSessionState.STOPPED
            ):
                await self.browser_runtime.stop()
                await self.browser_runtime.start()
            self._health = await self.adapter.check_session()
        except Exception as error:
            self._health = SessionHealth.unavailable(safe_failure_code(error))
        self.status_service.set_session_health(self._health)

    async def _run(self, name: str) -> None:
        async with self._lock:
            if name == "health":
                await self._probe()
                return
            if not self._health.healthy:
                return
            if name == "outbox" and os.getenv("FUSANHE_OUTBOUND_PAUSED", "false").lower() in {
                "1", "true", "yes",
            }:
                return
            operations: dict[str, Callable[[], Awaitable[Any]]] = {
                "orders": self.sync_engine.sync_orders,
                "conversations": self.sync_engine.sync_conversations_and_messages,
                "outbox": self.outbox_worker.run_once,
            }
            try:
                await operations[name]()
            finally:
                self._manual.discard(name)

    async def tick(self) -> None:
        await self._run("health")
        for name in ("conversations", "orders", "outbox"):
            await self._run(name)

    async def _loop(self, name: str) -> None:
        failures = 0
        while True:
            wake = self._wake.get(name)
            if wake is not None:
                wake.clear()
            try:
                await self._run(name)
                failures = 0
            except Exception as error:
                failures = min(failures + 1, 6)
                logger.warning("poll_failed resource=%s code=%s", name, safe_failure_code(error))
            delay = min(self._intervals[name] * 2**failures, 3600)
            if wake is None:
                await asyncio.sleep(delay)
            else:
                try:
                    await asyncio.wait_for(wake.wait(), delay)
                except TimeoutError:
                    pass

    async def start(self) -> None:
        if self._tasks:
            return
        await self._run("health")
        self._tasks = [
            asyncio.create_task(self._loop(name), name=f"mic-{name}")
            for name in self._intervals
        ]

    async def stop(self) -> None:
        tasks, self._tasks = self._tasks, []
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
