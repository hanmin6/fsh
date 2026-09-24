from __future__ import annotations

import asyncio
import os

import pytest

from mic_gateway.adapters.base import SourceCheckpoint
from mic_gateway.adapters.made_in_china import MadeInChinaAdapter
from mic_gateway.browser.runtime import BrowserRuntime
from mic_gateway.config import Settings


@pytest.mark.live
@pytest.mark.asyncio
async def test_authenticated_profile_can_read_a_validated_resource() -> None:
    if not os.environ.get("MIC_APP_DATA_DIR"):
        pytest.skip("MIC_APP_DATA_DIR is not configured")
    settings = Settings()  # type: ignore[call-arg]
    runtime = BrowserRuntime(settings)
    await runtime.start()
    try:
        adapter = MadeInChinaAdapter(runtime)
        health = await adapter.check_session()
        if not health.healthy and os.environ.get("MIC_LIVE_INTERACTIVE_LOGIN") == "1":
            await asyncio.to_thread(
                input,
                "Complete login in this browser, open the seller message page, "
                "then press Enter: ",
            )
            health = await adapter.check_session()
        assert health.healthy, health.detail_code

        orders = await adapter.list_orders(
            SourceCheckpoint(cursor=None, updated_after=None)
        )
        conversations = await adapter.list_conversations(
            SourceCheckpoint(cursor=None, updated_after=None)
        )

        assert isinstance(orders.items, tuple)
        assert isinstance(conversations.items, tuple)
    finally:
        await runtime.stop()
