from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from mic_gateway.adapters.made_in_china.adapter import (
    SiteContractError,
    parse_conversations,
)

FIXTURES = Path(__file__).parent / "fixtures"


def load_fixture(name: str) -> dict[str, object]:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def test_conversation_fixture_maps_stable_source_fields() -> None:
    result = parse_conversations(load_fixture("conversations-page.sanitized.json"))

    conversation = result.items[0]
    assert conversation.source_id == "conversation-001"
    assert conversation.buyer_reference == "buyer-001"
    assert conversation.inquiry_subject == "Synthetic inquiry subject"
    assert conversation.unread is True
    assert conversation.last_message_at == datetime(2026, 9, 19, 2, 45, tzinfo=UTC)
    assert conversation.source_updated_at.tzinfo is UTC
    assert result.next_cursor is None


def test_incompatible_conversation_shape_fails_closed() -> None:
    with pytest.raises(SiteContractError, match="conversation_list"):
        parse_conversations({"unexpected": []})
