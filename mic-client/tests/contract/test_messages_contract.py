from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from mic_gateway.adapters.made_in_china.adapter import SiteContractError, parse_messages
from mic_gateway.domain import Direction

FIXTURES = Path(__file__).parent / "fixtures"


def load_fixture(name: str) -> dict[str, object]:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def test_message_fixture_maps_initial_inquiry_exactly() -> None:
    result = parse_messages(
        load_fixture("messages-page.sanitized.json"),
        conversation_source_id="conversation-001",
    )

    message = result.items[0]
    assert message.source_id == "conversation-001:inquiry"
    assert message.conversation_source_id == "conversation-001"
    assert message.direction is Direction.INBOUND
    assert message.sender_label == "Buyer 001"
    assert message.content == "Synthetic inquiry message"
    assert message.source_created_at == datetime(2026, 9, 19, 2, 45, tzinfo=UTC)
    assert message.attachment_metadata == ()


def test_message_parser_selects_only_requested_conversation() -> None:
    result = parse_messages(
        load_fixture("messages-page.sanitized.json"),
        conversation_source_id="another-conversation",
    )

    assert result.items == ()


def test_incompatible_message_shape_fails_closed() -> None:
    with pytest.raises(SiteContractError, match="message_list"):
        parse_messages({"unexpected": []}, conversation_source_id="conversation-001")
