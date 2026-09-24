from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from urllib.parse import quote

import pytest

from mic_gateway.adapters.base import SourceCheckpoint
from mic_gateway.adapters.made_in_china import MadeInChinaAdapter, selectors
from mic_gateway.adapters.made_in_china.adapter import (
    SiteContractError,
    _source_timestamp_confidence,
    parse_trade_messenger_history,
)
from mic_gateway.domain import Direction

FIXTURES = Path(__file__).parents[1] / "contract" / "fixtures"
INQUIRY_CAPTURE = json.loads(
    (FIXTURES / "messages-page.sanitized.json").read_text(encoding="utf-8")
)


def _bubble(direction: str, content: str, minute: int, *, source_id: str) -> str:
    return (
        f'<div class="tm-message {direction}" data-message-id="{source_id}">'
        '<div class="tm-message-time-above-content">2026-09-22 09:'
        f'{minute:02d}</div><div class="tm-message-content">'
        f'<span class="tm-message-content-text">{content}</span>'
        "</div></div>"
    )


def _html(messages: str, *, button: bool = False, init_error: bool = False) -> str:
    load = (
        '<button class="tm-message-list-load-btn">Load earlier messages</button>'
        if button
        else ""
    )
    error = '<div class="init-error">Chat unavailable</div>' if init_error else ""
    return f'<div class="tm-message-list">{error}{messages}{load}</div>'


class FakeHistory:
    def __init__(
        self,
        states: list[str],
        *,
        no_progress: bool = False,
        remove_button_on_click: bool = False,
        control_ready_after_waits: int = 0,
        button_label: str = "Load earlier messages",
    ) -> None:
        self.states = states
        self.state_index = 0
        self.no_progress = no_progress
        self.remove_button_on_click = remove_button_on_click
        self.control_ready_after_waits = control_ready_after_waits
        self.control_waits = 0
        self.load_removed = False
        self.button_label = button_label
        self.clicks = 0

    @property
    def html(self) -> str:
        if self.control_waits < self.control_ready_after_waits:
            return self.states[self.state_index].replace(
                '<button class="tm-message-list-load-btn">Load earlier messages</button>', ""
            )
        return self.states[self.state_index]

    @property
    def button(self) -> bool:
        return (
            self.control_waits >= self.control_ready_after_waits
            and not self.load_removed
            and "tm-message-list-load-btn" in self.html
        )

    def click_load(self) -> None:
        self.clicks += 1
        if self.remove_button_on_click:
            self.load_removed = True
        if not self.no_progress:
            self.state_index = min(self.state_index + 1, len(self.states) - 1)


class FakeLocator:
    def __init__(self, page: FakeHistoryPage, selector: str, index: int = 0) -> None:
        self.page = page
        self.selector = selector
        self.index = index
        self.first = self

    async def count(self) -> int:
        if self.selector == selectors.CHAT_ROOT:
            return 1
        if self.selector == selectors.CHAT_INIT_ERROR:
            return int("init-error" in self.page.history.html)
        if self.selector == selectors.HISTORY_LOAD_BUTTON:
            return int(self.page.history.button)
        if self.selector == selectors.CHAT_RENDERED_ID_MARKER:
            return len(self.page.identity_markers)
        if self.selector in selectors.COMPOSER_SELECTORS:
            return int(self.page.composer_present)
        if self.selector in selectors.SEND_BUTTON_SELECTORS:
            return int(self.page.send_button_present)
        return 0

    async def is_visible(self) -> bool:
        if self.selector == selectors.CHAT_RENDERED_ID_MARKER:
            return self.page.identity_markers[self.index][1]
        return await self.count() > 0

    async def get_attribute(self, name: str) -> str | None:
        if (
            self.selector == selectors.CHAT_RENDERED_ID_MARKER
            and name == "inquiry-id"
        ):
            return self.page.identity_markers[self.index][0]
        return None

    async def inner_text(self) -> str:
        if self.selector == selectors.HISTORY_LOAD_BUTTON:
            return self.page.history.button_label
        return ""

    async def inner_html(self) -> str:
        assert self.selector == selectors.CHAT_ROOT
        return self.page.history.html

    async def click(self) -> None:
        if self.selector == selectors.HISTORY_LOAD_BUTTON:
            self.page.history.click_load()
            if (
                self.page.identity_change_after_history_clicks is not None
                and self.page.history.clicks >= self.page.identity_change_after_history_clicks
            ):
                self.page.identity_markers = [("another-conversation", True)]
        elif self.selector in selectors.SEND_BUTTON_SELECTORS:
            self.page.send_clicks += 1
        else:
            self.page.clicks += 1

    async def fill(self, _content: str) -> None:
        self.page.fill_count += 1
        if self.page.identity_change_on_fill:
            self.page.identity_markers = [("another-conversation", True)]

    async def is_disabled(self) -> bool:
        return False

    def nth(self, index: int) -> FakeLocator:
        return FakeLocator(self.page, self.selector, index)

    async def wait_for(self, *, state: str, timeout: int) -> None:  # noqa: ASYNC109
        del timeout
        assert state == "visible"
        if await self.count() == 0:
            raise AssertionError("expected chat root to be visible")


class FakeHistoryPage:
    url = "about:blank"

    def __init__(
        self,
        history: FakeHistory,
        identity_markers: list[tuple[str, bool]] | None = None,
        *,
        identity_change_after_history_clicks: int | None = None,
        identity_change_on_fill: bool = False,
        composer_present: bool = False,
        send_button_present: bool = False,
    ) -> None:
        self.history = history
        self.identity_markers = (
            [("conversation-001", True)]
            if identity_markers is None
            else identity_markers
        )
        self.identity_change_after_history_clicks = identity_change_after_history_clicks
        self.identity_change_on_fill = identity_change_on_fill
        self.composer_present = composer_present
        self.send_button_present = send_button_present
        self.clicks = 0
        self.fill_count = 0
        self.send_clicks = 0
        self.located_selectors: list[str] = []
        self.navigated_to: str | None = None

    async def goto(self, url: str, **_kwargs: Any) -> None:
        self.navigated_to = url
        self.url = url

    def locator(self, selector: str) -> FakeLocator:
        self.located_selectors.append(selector)
        return FakeLocator(self, selector)

    async def wait_for_timeout(self, milliseconds: int) -> None:
        if milliseconds == 100:
            self.history.control_waits += 1


class FakeRuntime:
    def __init__(self, page: FakeHistoryPage) -> None:
        self.page = page
        self.settings = SimpleNamespace(seller_url="https://membercenter.made-in-china.com/")

    async def run_serialized(self, operation: Any) -> Any:
        return await operation(self.page)


def _adapter(
    states: list[str],
    *,
    no_progress: bool = False,
    remove_button_on_click: bool = False,
    control_ready_after_waits: int = 0,
    button_label: str = "Load earlier messages",
    stub_identity: bool = True,
    identity_markers: list[tuple[str, bool]] | None = None,
    identity_change_after_history_clicks: int | None = None,
    identity_change_on_fill: bool = False,
    composer_present: bool = False,
    send_button_present: bool = False,
) -> tuple[MadeInChinaAdapter, FakeHistoryPage]:
    history = FakeHistory(
        states,
        no_progress=no_progress,
        remove_button_on_click=remove_button_on_click,
        control_ready_after_waits=control_ready_after_waits,
        button_label=button_label,
    )
    page = FakeHistoryPage(
        history,
        identity_markers,
        identity_change_after_history_clicks=identity_change_after_history_clicks,
        identity_change_on_fill=identity_change_on_fill,
        composer_present=composer_present,
        send_button_present=send_button_present,
    )
    adapter = MadeInChinaAdapter(FakeRuntime(page))  # type: ignore[arg-type]

    async def require_session(_page: Any) -> None:
        return None

    async def read_contract(_page: Any, contract: Any) -> dict[str, Any]:
        assert contract is selectors.MESSAGES
        return INQUIRY_CAPTURE

    adapter._require_session = require_session  # type: ignore[method-assign]
    adapter._read_contract = read_contract  # type: ignore[method-assign]
    if stub_identity:
        async def identity_confirmed(_page: Any, _source_id: str) -> bool:
            return True

        adapter._conversation_identity_confirmed = identity_confirmed  # type: ignore[method-assign]
    return adapter, page


@pytest.mark.asyncio
async def test_list_messages_opens_conversation_loads_all_history_and_keeps_inquiry_once() -> None:
    inquiry = _bubble(
        "tm-message-recv",
        "Synthetic inquiry message",
        10,
        source_id="conversation-001:inquiry",
    )
    earlier = _bubble(
        "tm-message-recv", "Synthetic earlier buyer message", 8, source_id="earlier"
    )
    oldest = _bubble("tm-message-recv", "Synthetic oldest message", 7, source_id="oldest")
    reply = _bubble("tm-message-send", "Synthetic seller reply", 12, source_id="reply")
    adapter, page = _adapter(
        [
            _html(inquiry + reply, button=True),
            _html(earlier + inquiry + reply, button=True),
            _html(oldest + earlier + inquiry + reply),
        ]
    )

    result = await adapter.list_messages(
        "conversation-001", SourceCheckpoint(cursor=None, updated_after=None)
    )

    assert page.navigated_to == (
        "https://membercenter.made-in-china.com/message/index.html"
        "#inbox/conversation-001..from=list"
    )
    assert [message.content for message in result.items] == [
        "Synthetic inquiry message",
        "Synthetic oldest message",
        "Synthetic earlier buyer message",
        "Synthetic seller reply",
    ]
    assert [message.direction for message in result.items] == [
        Direction.INBOUND,
        Direction.INBOUND,
        Direction.INBOUND,
        Direction.OUTBOUND,
    ]
    assert [message.source_id for message in result.items] == [
        "conversation-001:inquiry",
        "oldest",
        "earlier",
        "reply",
    ]
    assert [message.source_sequence for message in result.items] == [1, 2, 3, 4]
    assert page.history.clicks == 2
    assert result.history_complete is True
    assert result.items[0].source_timestamp_raw == "20260919104500"
    assert result.items[0].source_timestamp_confidence == "high"
    assert result.items[1].source_timestamp_raw == "2026-09-22 09:07"
    assert result.items[1].source_timestamp_confidence == "high"


@pytest.mark.asyncio
async def test_list_messages_fails_closed_when_load_button_makes_no_progress() -> None:
    adapter, _page = _adapter(
        [_html(_bubble("tm-message-recv", "Inquiry", 10, source_id="i"), button=True)],
        no_progress=True,
    )

    with pytest.raises(SiteContractError, match="history_no_progress"):
        await adapter.list_messages(
            "conversation-001", SourceCheckpoint(cursor=None, updated_after=None)
        )


@pytest.mark.asyncio
async def test_list_messages_rejects_identity_switch_during_history_paging() -> None:
    current = _bubble("tm-message-recv", "Current synthetic", 10, source_id="current")
    older = _bubble("tm-message-recv", "Older synthetic", 8, source_id="older")
    adapter, _page = _adapter(
        [_html(current, button=True), _html(older + current)],
        stub_identity=False,
        identity_change_after_history_clicks=1,
    )

    with pytest.raises(SiteContractError, match="identity changed"):
        await adapter.list_messages(
            "conversation-001", SourceCheckpoint(cursor=None, updated_after=None)
        )


@pytest.mark.asyncio
async def test_send_rechecks_identity_after_fill_before_send_click() -> None:
    adapter, page = _adapter(
        [_html("<div>synthetic root</div>")],
        stub_identity=False,
        identity_change_on_fill=True,
        composer_present=True,
        send_button_present=True,
    )
    page.url = (
        "https://membercenter.made-in-china.com/message/index.html"
        "#inbox/conversation-001..from=list"
    )

    result = await adapter.send_message("conversation-001", "Synthetic outbound")

    assert result.code == "conversation_identity_unconfirmed"
    assert page.fill_count == 1
    assert page.send_clicks == 0


@pytest.mark.asyncio
async def test_open_conversation_escapes_source_id_in_url_and_avoids_css_interpolation() -> None:
    source_id = "conv' ] #/?[].."
    adapter, page = _adapter(
        [_html("<div>synthetic root</div>")],
        stub_identity=False,
        identity_markers=[(source_id, True)],
    )

    assert await adapter._open_conversation(page, source_id)

    encoded_source_id = quote(source_id, safe="").replace(".", "%2E")
    expected_fragment = f"#inbox/{encoded_source_id}..from=list"
    assert page.navigated_to is not None and page.navigated_to.endswith(expected_fragment)
    assert all(source_id not in selector for selector in page.located_selectors)
    assert await adapter._conversation_identity_confirmed(page, source_id)


@pytest.mark.asyncio
async def test_list_messages_preserves_distinct_same_text_inbound_message() -> None:
    repeated = _bubble(
        "tm-message-recv", "Synthetic inquiry message", 10, source_id="later-message"
    )
    repeated_again = _bubble(
        "tm-message-recv", "Synthetic inquiry message", 11, source_id="later-message-2"
    )
    adapter, _page = _adapter(
        [_html(repeated, button=True), _html(repeated + repeated_again)]
    )

    result = await adapter.list_messages(
        "conversation-001", SourceCheckpoint(cursor=None, updated_after=None)
    )

    assert [message.content for message in result.items] == [
        "Synthetic inquiry message",
        "Synthetic inquiry message",
        "Synthetic inquiry message",
    ]
    assert [message.source_id for message in result.items] == [
        "conversation-001:inquiry",
        "later-message",
        "later-message-2",
    ]


@pytest.mark.asyncio
async def test_list_messages_fails_closed_without_rendered_identity_marker() -> None:
    adapter, _page = _adapter(
        [_html(_bubble("tm-message-recv", "Synthetic message", 10, source_id="m"))],
        stub_identity=False,
        identity_markers=[],
    )

    with pytest.raises(SiteContractError, match="history_incomplete.*identity unconfirmed"):
        await adapter.list_messages(
            "conversation-001", SourceCheckpoint(cursor=None, updated_after=None)
        )


@pytest.mark.asyncio
async def test_list_messages_rejects_load_button_disappearance_without_new_bubbles() -> None:
    initial = _html(_bubble("tm-message-recv", "Inquiry", 10, source_id="i"), button=True)
    adapter, _page = _adapter([initial], remove_button_on_click=True)

    with pytest.raises(SiteContractError, match="history_no_progress"):
        await adapter.list_messages(
            "conversation-001", SourceCheckpoint(cursor=None, updated_after=None)
        )


@pytest.mark.asyncio
async def test_conversation_identity_does_not_accept_url_id_prefix_collision() -> None:
    adapter, page = _adapter([_html("<div>old synthetic chat</div>")], stub_identity=False)
    page.url = "https://membercenter.made-in-china.com/message/index.html#inbox/1234..from=list"

    assert not await adapter._conversation_identity_confirmed(page, "123")
    assert await adapter._open_conversation(page, "123")
    assert page.navigated_to == (
        "https://membercenter.made-in-china.com/message/index.html#inbox/123..from=list"
    )


@pytest.mark.asyncio
async def test_conversation_identity_rejects_stale_root_after_target_url_changes() -> None:
    adapter, page = _adapter(
        [_html(_bubble("tm-message-recv", "Old synthetic conversation", 10, source_id="old"))],
        stub_identity=False,
        identity_markers=[("another-conversation", True)],
    )
    page.url = "https://membercenter.made-in-china.com/message/index.html#inbox/target..from=list"

    assert not await adapter._conversation_identity_confirmed(page, "target")


@pytest.mark.asyncio
async def test_send_fails_closed_when_target_rendered_identity_is_unavailable() -> None:
    adapter, page = _adapter(
        [_html("<div>old synthetic chat</div>")],
        stub_identity=False,
        identity_markers=[("another-conversation", True)],
    )
    page.url = "https://membercenter.made-in-china.com/message/index.html#inbox/target..from=list"

    result = await adapter.send_message("target", "Synthetic outbound text")

    assert result.code == "conversation_identity_unconfirmed"
    assert page.fill_count == 0
    assert page.clicks == 0


@pytest.mark.asyncio
async def test_conversation_identity_requires_one_visible_matching_rendered_marker() -> None:
    cases = [
        ([("conversation-001", True)], True),
        ([("another-conversation", True)], False),
        ([], False),
        ([("conversation-001", False)], False),
        ([("conversation-001", True), ("conversation-001", True)], False),
    ]
    for markers, expected in cases:
        adapter, page = _adapter(
            [_html("<div>synthetic root</div>")],
            stub_identity=False,
            identity_markers=markers,
        )
        page.url = (
            "https://membercenter.made-in-china.com/message/index.html"
            "#inbox/conversation-001..from=list"
        )

        assert await adapter._conversation_identity_confirmed(page, "conversation-001") is expected


@pytest.mark.asyncio
async def test_history_waits_for_load_control_to_mount_after_chat_root() -> None:
    current = _bubble("tm-message-recv", "Current synthetic message", 10, source_id="current")
    older = _bubble("tm-message-recv", "Older synthetic message", 8, source_id="older")
    adapter, page = _adapter(
        [_html(current, button=True), _html(older + current)],
        control_ready_after_waits=2,
        stub_identity=False,
    )

    result = await adapter._load_complete_trade_messenger_history(page, "conversation-001")

    assert page.history.control_waits >= 2
    assert "Older synthetic message" in result


@pytest.mark.asyncio
async def test_history_accepts_observed_chinese_load_control_label() -> None:
    current = _bubble("tm-message-recv", "Current synthetic message", 10, source_id="current")
    older = _bubble("tm-message-recv", "Older synthetic message", 8, source_id="older")
    adapter, page = _adapter(
        [_html(current, button=True), _html(older + current)],
        button_label="查看更多消息",
    )

    result = await adapter._load_complete_trade_messenger_history(page, "conversation-001")

    assert "Older synthetic message" in result
    assert page.history.clicks == 1


@pytest.mark.asyncio
async def test_history_fails_closed_when_load_control_never_mounts() -> None:
    message = _bubble("tm-message-recv", "Only synthetic", 10, source_id="m")
    adapter, page = _adapter([_html(message)])

    with pytest.raises(SiteContractError, match="history_incomplete.*control readiness"):
        await adapter._load_complete_trade_messenger_history(page, "conversation-001")

    assert page.history.control_waits > 0


@pytest.mark.parametrize(
    ("timestamp", "expected_confidence"),
    [
        ("2026-09-22 09:15", "high"),
        ("2026-09-22", "medium"),
        ("09:15", "low"),
    ],
)
def test_trade_messenger_timestamp_confidence_uses_source_precision(
    timestamp: str, expected_confidence: str
) -> None:
    if timestamp == "09:15":
        assert _source_timestamp_confidence(timestamp) == expected_confidence
        return
    html = _bubble(
        "tm-message-recv", "Synthetic time confidence", 15, source_id="m"
    ).replace("2026-09-22 09:15", timestamp)

    message = parse_trade_messenger_history(
        html,
        conversation_source_id="conversation-001",
        account_handle="seller",
        history_complete=True,
    )[0]

    assert message.source_timestamp_raw == timestamp
    assert message.source_timestamp_confidence == expected_confidence


@pytest.mark.asyncio
async def test_list_messages_fails_closed_when_load_control_semantics_are_unrecognized() -> None:
    adapter, page = _adapter(
        [_html(_bubble("tm-message-recv", "Inquiry", 10, source_id="i"), button=True)],
        button_label="Show more",
    )

    with pytest.raises(SiteContractError, match="history_incomplete.*unrecognized"):
        await adapter.list_messages(
            "conversation-001", SourceCheckpoint(cursor=None, updated_after=None)
        )

    assert page.history.clicks == 0


@pytest.mark.asyncio
async def test_list_messages_fails_closed_when_history_exceeds_click_bound() -> None:
    states = [
        _html(
            _bubble("tm-message-recv", f"Message {index}", 10, source_id=f"m{index}"),
            button=True,
        )
        for index in range(selectors.MESSAGE_HISTORY_MAX_CLICKS + 2)
    ]
    adapter, page = _adapter(states)

    with pytest.raises(SiteContractError, match="history_incomplete"):
        await adapter.list_messages(
            "conversation-001", SourceCheckpoint(cursor=None, updated_after=None)
        )

    assert page.history.clicks == selectors.MESSAGE_HISTORY_MAX_CLICKS


@pytest.mark.asyncio
async def test_list_messages_fails_closed_on_trade_messenger_init_error() -> None:
    adapter, _page = _adapter([_html("", init_error=True)])

    with pytest.raises(SiteContractError, match="init_error"):
        await adapter.list_messages(
            "conversation-001", SourceCheckpoint(cursor=None, updated_after=None)
        )
