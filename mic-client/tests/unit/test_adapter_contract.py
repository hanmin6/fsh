from __future__ import annotations

from datetime import UTC, datetime

import pytest

from mic_gateway.adapters.base import (
    SendAttempt,
    SessionHealth,
    SiteAdapter,
    SourceCheckpoint,
    SourcePage,
)
from mic_gateway.adapters.fake import FakeSiteAdapter
from mic_gateway.domain import Direction, SourceConversation, SourceMessage


def conversation(source_id: str) -> SourceConversation:
    return SourceConversation(
        source_id=source_id,
        buyer_reference="buyer-1",
        inquiry_subject="Question",
        unread=True,
        last_message_at=datetime(2026, 9, 19, 12, 0, tzinfo=UTC),
        source_updated_at=datetime(2026, 9, 19, 12, 0, tzinfo=UTC),
        raw_snapshot={},
    )


def outbound_message() -> SourceMessage:
    return SourceMessage(
        source_id="message-1",
        conversation_source_id="conversation-1",
        direction=Direction.OUTBOUND,
        sender_label="seller",
        content="Hello",
        attachment_metadata=(),
        source_created_at=datetime(2026, 9, 19, 12, 1, tzinfo=UTC),
        raw_snapshot={},
    )


@pytest.mark.asyncio
async def test_fake_adapter_pages_from_checkpoint() -> None:
    adapter = FakeSiteAdapter(
        conversation_pages={
            None: SourcePage(
                items=(conversation("conversation-1"),),
                next_cursor="conversation-page-2",
            ),
            "conversation-page-2": SourcePage(
                items=(conversation("conversation-2"),),
                next_cursor=None,
            ),
        }
    )

    first = await adapter.list_conversations(
        SourceCheckpoint(cursor=None, updated_after=None)
    )
    second = await adapter.list_conversations(
        SourceCheckpoint(cursor=first.next_cursor, updated_after=None)
    )

    assert first.items[0].source_id == "conversation-1"
    assert first.next_cursor == "conversation-page-2"
    assert second.items[0].source_id == "conversation-2"
    assert [call.cursor for call in adapter.conversation_checkpoints] == [
        None,
        "conversation-page-2",
    ]


@pytest.mark.asyncio
async def test_fake_adapter_can_model_uncertain_send() -> None:
    adapter = FakeSiteAdapter()
    adapter.next_send = SendAttempt.uncertain("confirmation_missing")

    result = await adapter.send_message("conversation-1", "Hello")

    assert result.outcome == "uncertain"
    assert result.code == "confirmation_missing"
    assert adapter.send_calls == [("conversation-1", "Hello")]


@pytest.mark.asyncio
async def test_fake_adapter_exposes_session_and_reconciliation_controls() -> None:
    adapter = FakeSiteAdapter()
    adapter.session_health = SessionHealth.verification_required()
    adapter.outbound_match = outbound_message()

    health = await adapter.check_session()
    match = await adapter.find_outbound_match(
        "conversation-1",
        "digest-1",
        datetime(2026, 9, 19, 12, 0, tzinfo=UTC),
    )

    assert health.state == "verification_required"
    assert health.requires_operator is True
    assert match is adapter.outbound_match
    assert adapter.match_calls[0][1] == "digest-1"


@pytest.mark.asyncio
async def test_fake_adapter_injects_one_shot_failures() -> None:
    adapter = FakeSiteAdapter()
    adapter.fail_next("list_orders", RuntimeError("source unavailable"))

    with pytest.raises(RuntimeError, match="source unavailable"):
        await adapter.list_orders(SourceCheckpoint(cursor=None, updated_after=None))

    page = await adapter.list_orders(SourceCheckpoint(cursor=None, updated_after=None))
    assert page.items == ()


def test_fake_satisfies_runtime_protocol_without_playwright_import() -> None:
    adapter = FakeSiteAdapter()

    assert isinstance(adapter, SiteAdapter)
    assert "playwright" not in adapter.__class__.__module__


def test_history_page_cannot_claim_complete_while_another_page_remains() -> None:
    with pytest.raises(ValueError, match="history_complete requires next_cursor to be None"):
        SourcePage(items=(), next_cursor="older-page", history_complete=True)
