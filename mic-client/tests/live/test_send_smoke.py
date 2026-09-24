from __future__ import annotations

import os
from datetime import UTC, datetime

import pytest

from mic_gateway.adapters.base import SourceCheckpoint
from mic_gateway.adapters.made_in_china import MadeInChinaAdapter
from mic_gateway.browser.runtime import BrowserRuntime
from mic_gateway.config import Settings


@pytest.mark.live
@pytest.mark.live_send
@pytest.mark.asyncio
async def test_explicit_test_conversation_accepts_one_acknowledgement() -> None:
    conversation_id = os.environ.get("MIC_LIVE_TEST_CONVERSATION_ID")
    recipient_label = os.environ.get("MIC_LIVE_TEST_RECIPIENT_LABEL")
    if not conversation_id or not recipient_label:
        pytest.skip("live-send conversation and recipient are not configured")
    settings = Settings()  # type: ignore[call-arg]
    runtime = BrowserRuntime(settings)
    await runtime.start()
    try:
        adapter = MadeInChinaAdapter(runtime)
        conversations = await adapter.list_conversations(
            SourceCheckpoint(cursor=None, updated_after=None)
        )
        target = next(
            (item for item in conversations.items if item.source_id == conversation_id),
            None,
        )
        assert target is not None
        assert target.buyer_reference == recipient_label

        unique = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        content = f"Hello, thank you for contacting us. Reference {unique}."
        result = await adapter.send_message(conversation_id, content)

        assert result.outcome == "sent"
    finally:
        await runtime.stop()
