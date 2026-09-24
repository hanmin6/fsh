from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from mic_gateway.adapters.base import SourceCheckpoint
from mic_gateway.adapters.made_in_china import MadeInChinaAdapter, selectors


class FakeLocator:
    def __init__(self, page: DelayedSessionPage, selector: str) -> None:
        self.page = page
        self.selector = selector
        self.first = self

    async def count(self) -> int:
        if self.selector == selectors.CONVERSATIONS.page_marker and self.page.polls >= 2:
            return 1
        return 0

    async def is_visible(self) -> bool:
        return await self.count() == 1


class DelayedSessionPage:
    url = "https://membercenter.made-in-china.com/"

    def __init__(self) -> None:
        self.polls = 0
        self.navigated_to: str | None = None

    async def goto(self, url: str, **_kwargs: Any) -> None:
        self.navigated_to = url
        return None

    def locator(self, selector: str) -> FakeLocator:
        return FakeLocator(self, selector)

    async def wait_for_timeout(self, _milliseconds: int) -> None:
        self.polls += 1


class FakeRuntime:
    def __init__(self, page: DelayedSessionPage) -> None:
        self.page = page
        self.settings = SimpleNamespace(
            seller_url="https://membercenter.made-in-china.com/"
        )
        self.marked: str | None = None

    async def run_serialized(self, operation: Any) -> Any:
        return await operation(self.page)

    def mark_authenticated(self) -> None:
        self.marked = "authenticated"

    def mark_operator_action_required(self) -> None:
        self.marked = "operator_action_required"

    def mark_site_contract_error(self) -> None:
        self.marked = "site_contract_error"


class FakeResponse:
    url = "https://membercenter.made-in-china.com/message.do?operation=list"
    status = 200
    headers = {"content-type": "application/json;charset=UTF-8"}
    request = SimpleNamespace(method="GET")

    async def json(self) -> dict[str, object]:
        return {
            "total": 1,
            "unread": 1,
            "unreply": 1,
            "messages": [
                {
                    "id": "conversation-live-1",
                    "contactNo": "buyer-live-1",
                    "contactName": "Buyer Live",
                    "subject": "Need product details",
                    "content": "Please share more information",
                    "time": "20260919104500",
                    "isRead": False,
                    "attachList": [],
                }
            ],
            "time": "20260919104500",
        }


class AuthenticatedReadPage(DelayedSessionPage):
    def __init__(self) -> None:
        super().__init__()
        self.polls = 2
        self._observer: Any = None

    def on(self, event: str, observer: Any) -> None:
        assert event == "response"
        self._observer = observer

    def remove_listener(self, event: str, observer: Any) -> None:
        assert event == "response"
        assert observer is self._observer

    async def goto(self, url: str, **_kwargs: Any) -> None:
        self.navigated_to = url
        if self._observer is not None:
            self._observer(FakeResponse())


@pytest.mark.asyncio
async def test_session_probe_waits_for_async_authenticated_marker() -> None:
    page = DelayedSessionPage()
    runtime = FakeRuntime(page)
    adapter = MadeInChinaAdapter(runtime)  # type: ignore[arg-type]

    health = await adapter.check_session()

    assert health.healthy
    assert runtime.marked == "authenticated"
    assert page.polls == 2
    assert page.navigated_to == (
        "https://membercenter.made-in-china.com/message/index.html"
    )


@pytest.mark.asyncio
async def test_adapter_preserves_business_fields_but_sanitizes_raw_snapshot() -> None:
    runtime = FakeRuntime(AuthenticatedReadPage())
    adapter = MadeInChinaAdapter(runtime)  # type: ignore[arg-type]

    result = await adapter.list_conversations(
        SourceCheckpoint(cursor=None, updated_after=None)
    )

    conversation = result.items[0]
    assert conversation.buyer_reference == "buyer-live-1"
    assert conversation.inquiry_subject == "Need product details"
    assert conversation.raw_snapshot["contactNo"] == "Contact 001"
    assert conversation.raw_snapshot["subject"] == "Message 001"


@pytest.mark.asyncio
async def test_session_probe_forces_refresh_when_idle() -> None:
    """When the browser stays on the conversation page for > 300s, check_session forces a reload/navigation."""
    page = DelayedSessionPage()
    page.url = "https://membercenter.made-in-china.com/message/index.html"
    page.polls = 2  # causes locator count == 1, so detected is healthy
    runtime = FakeRuntime(page)
    adapter = MadeInChinaAdapter(runtime)  # type: ignore[arg-type]
    adapter._last_refresh_at = 1.0  # simulated old timestamp

    health = await adapter.check_session()
    assert health.healthy
    assert page.navigated_to == "https://membercenter.made-in-china.com/message/index.html"

