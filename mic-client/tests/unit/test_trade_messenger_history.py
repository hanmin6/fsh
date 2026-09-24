from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

import pytest

from mic_gateway.adapters.made_in_china import adapter
from mic_gateway.adapters.made_in_china.adapter import SiteContractError
from mic_gateway.domain import Direction, SourceMessage

FIXTURES = Path(__file__).parents[1] / "contract" / "fixtures"


def _fixture() -> str:
    return (FIXTURES / "trademessenger-history.sanitized.html").read_text(encoding="utf-8")


def _bubble(
    direction: str, content: str, time: str, sender: str, *, attachment: str = ""
) -> str:
    return (
        f'<div class="tm-message {direction}">'
        f'<div class="tm-message-from-user-name">{sender}</div>'
        f'<div class="tm-message-time-above-content">{time}</div>'
        f'<div class="tm-message-content"><span class="tm-message-content-text">'
        f'{content}</span>{attachment}</div></div>'
    )


def _parse(*args: object, **kwargs: object):
    parser = getattr(adapter, "parse_trade_messenger_history", None)
    assert callable(parser), "TradeMessenger DOM parser has not been implemented"
    return parser(*args, **kwargs)


def test_dom_parser_extracts_visible_bilateral_bubbles_in_order_and_skips_system_rows() -> None:
    result = _parse(
        _fixture(), conversation_source_id="conversation-001", account_handle="seller-01",
        history_complete=True,
    )

    assert [message.content for message in result] == [
        "Synthetic buyer message",
        "Synthetic seller reply",
    ]
    assert [message.direction for message in result] == [Direction.INBOUND, Direction.OUTBOUND]
    assert [message.sender_label for message in result] == ["Buyer 001", "Seller 001"]
    assert [message.source_timestamp_raw for message in result] == [
        " 2026-09-22 09:15 ", " 2026-09-22 09:17 "
    ]
    assert [message.source_sequence for message in result] == [1, 2]
    assert result[0].attachment_metadata == ({"name": "spec-sheet.pdf", "size": 2048},)
    assert "invalid.example" not in repr(result[0].attachment_metadata)


def test_dom_parser_generates_repeatable_ids_when_source_ids_are_absent() -> None:
    kwargs = dict(
        conversation_source_id="conversation-001", account_handle="seller-01",
        history_complete=True,
    )

    first = _parse(_fixture(), **kwargs)
    second = _parse(_fixture(), **kwargs)

    assert [message.source_id for message in first] == [message.source_id for message in second]
    assert len({message.source_id for message in first}) == len(first)
    assert all(message.source_id and message.source_id.startswith("tm-") for message in first)


def test_fallback_ids_remain_stable_when_nonidentical_messages_are_reordered() -> None:
    first_html = _bubble("tm-message-recv", "First", "2026-09-22 09:15", "Buyer") + _bubble(
        "tm-message-send", "Second", "2026-09-22 09:17", "Seller"
    )
    reordered_html = _bubble(
        "tm-message-send", "Second", "2026-09-22 09:17", "Seller"
    ) + _bubble("tm-message-recv", "First", "2026-09-22 09:15", "Buyer")
    kwargs = dict(
        conversation_source_id="conversation-001", account_handle="seller-01",
        history_complete=True,
    )

    first = _parse(first_html, **kwargs)
    reordered = _parse(reordered_html, **kwargs)

    assert {message.content: message.source_id for message in first} == {
        message.content: message.source_id for message in reordered
    }


def test_identical_fallback_messages_get_distinct_stable_occurrence_ids() -> None:
    bubble = _bubble("tm-message-recv", "Repeated", "2026-09-22 09:15", "Buyer")
    html = bubble + bubble
    kwargs = dict(
        conversation_source_id="conversation-001", account_handle="seller-01",
        history_complete=True,
    )

    first = _parse(html, **kwargs)
    second = _parse(html, **kwargs)

    first_ids = [message.source_id for message in first]
    assert len(set(first_ids)) == 2
    assert first_ids == [message.source_id for message in second]


def test_fallback_ids_stay_with_attachment_metadata_when_bubbles_are_reordered() -> None:
    first_attachment = (
        '<a class="tm-message-attachment" data-file-name="first.pdf" '
        'data-file-size="1024" href="https://invalid.example/a?token=secret-a">first</a>'
    )
    second_attachment = (
        '<a class="tm-message-attachment" data-file-name="second.pdf" '
        'data-file-size="2048" href="https://invalid.example/b?token=secret-b">second</a>'
    )
    first_html = _bubble(
        "tm-message-recv", "Same text", "2026-09-22 09:15", "Buyer",
        attachment=first_attachment,
    ) + _bubble(
        "tm-message-recv", "Same text", "2026-09-22 09:15", "Buyer",
        attachment=second_attachment,
    )
    reordered_html = _bubble(
        "tm-message-recv", "Same text", "2026-09-22 09:15", "Buyer",
        attachment=second_attachment,
    ) + _bubble(
        "tm-message-recv", "Same text", "2026-09-22 09:15", "Buyer",
        attachment=first_attachment,
    )
    kwargs = dict(
        conversation_source_id="conversation-001", account_handle="seller-01",
        history_complete=True,
    )

    first = _parse(first_html, **kwargs)
    reordered = _parse(reordered_html, **kwargs)

    def ids_by_attachment(messages: Sequence[SourceMessage]) -> dict[str, str | None]:
        return {
            message.attachment_metadata[0]["name"]: message.source_id
            for message in messages
        }

    assert ids_by_attachment(first) == ids_by_attachment(reordered)
    assert all("invalid.example" not in (message.source_id or "") for message in first)


@pytest.mark.parametrize("direction_classes", ["tm-message-send tm-message-recv", ""])
def test_dom_parser_rejects_ambiguous_or_missing_direction(direction_classes: str) -> None:
    html = _bubble(direction_classes, "Ambiguous", "2026-09-22 09:15", "Unknown")

    with pytest.raises(SiteContractError, match="direction"):
        _parse(
            html, conversation_source_id="conversation-001", account_handle="seller-01",
            history_complete=True,
        )


@pytest.mark.parametrize(
    ("html", "history_complete", "error"),
    [
        ('<div class="init-error">Chat unavailable</div>', True, "init_error"),
        (_fixture(), False, "history_incomplete"),
    ],
)
def test_dom_parser_fails_closed_for_unavailable_or_incomplete_history(
    html: str, history_complete: bool, error: str
) -> None:
    with pytest.raises(SiteContractError, match=error):
        _parse(
            html, conversation_source_id="conversation-001", account_handle="seller-01",
            history_complete=history_complete,
        )
