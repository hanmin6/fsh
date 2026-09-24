from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import pytest

from mic_gateway.browser.runtime import BrowserRuntime
from mic_gateway.config import Settings


class SerializationLauncher:
    class Driver:
        async def stop(self) -> None:
            return None

    class Context:
        pages = [object()]

        async def close(self) -> None:
            return None

    async def launch(self, user_data_dir: Path, *, headless: bool) -> tuple[Any, Any]:
        return self.Driver(), self.Context()


@pytest.mark.asyncio
async def test_operations_never_overlap(tmp_path: Path) -> None:
    runtime = BrowserRuntime(Settings(app_data_dir=tmp_path), launcher=SerializationLauncher())
    await runtime.start()
    active = 0
    peak = 0

    async def operation(_: object) -> None:
        nonlocal active, peak
        active += 1
        peak = max(peak, active)
        await asyncio.sleep(0.01)
        active -= 1

    await asyncio.gather(*(runtime.run_serialized(operation) for _ in range(5)))

    assert peak == 1
