from __future__ import annotations

from collections import defaultdict, deque
from collections.abc import Mapping
from datetime import datetime

from mic_gateway.adapters.base import (
    SendAttempt,
    SessionHealth,
    SourceCheckpoint,
    SourcePage,
)
from mic_gateway.domain import SourceConversation, SourceMessage, SourceOrder


class FakeSiteAdapter:
    def __init__(
        self,
        *,
        order_pages: Mapping[str | None, SourcePage[SourceOrder]] | None = None,
        conversation_pages: Mapping[
            str | None, SourcePage[SourceConversation]
        ]
        | None = None,
        message_pages: Mapping[
            tuple[str, str | None], SourcePage[SourceMessage]
        ]
        | None = None,
    ) -> None:
        self.order_pages = dict(order_pages or {})
        self.conversation_pages = dict(conversation_pages or {})
        self.message_pages = dict(message_pages or {})
        self.session_health = SessionHealth.available()
        self.next_send = SendAttempt.sent()
        self.outbound_match: SourceMessage | None = None

        self.session_checks = 0
        self.order_checkpoints: list[SourceCheckpoint] = []
        self.conversation_checkpoints: list[SourceCheckpoint] = []
        self.message_checkpoints: list[tuple[str, SourceCheckpoint]] = []
        self.send_calls: list[tuple[str, str]] = []
        self.match_calls: list[tuple[str, str, datetime]] = []
        self._failures: defaultdict[str, deque[Exception]] = defaultdict(deque)

    def fail_next(self, method: str, error: Exception) -> None:
        self._failures[method].append(error)

    def _raise_injected(self, method: str) -> None:
        failures = self._failures[method]
        if failures:
            raise failures.popleft()

    async def check_session(self) -> SessionHealth:
        self.session_checks += 1
        self._raise_injected("check_session")
        return self.session_health

    async def list_orders(
        self, checkpoint: SourceCheckpoint
    ) -> SourcePage[SourceOrder]:
        self.order_checkpoints.append(checkpoint)
        self._raise_injected("list_orders")
        return self.order_pages.get(checkpoint.cursor, SourcePage(items=(), next_cursor=None))

    async def list_conversations(
        self, checkpoint: SourceCheckpoint
    ) -> SourcePage[SourceConversation]:
        self.conversation_checkpoints.append(checkpoint)
        self._raise_injected("list_conversations")
        return self.conversation_pages.get(
            checkpoint.cursor, SourcePage(items=(), next_cursor=None)
        )

    async def list_messages(
        self,
        conversation_source_id: str,
        checkpoint: SourceCheckpoint,
    ) -> SourcePage[SourceMessage]:
        self.message_checkpoints.append((conversation_source_id, checkpoint))
        self._raise_injected("list_messages")
        return self.message_pages.get(
            (conversation_source_id, checkpoint.cursor),
            SourcePage(items=(), next_cursor=None),
        )

    async def send_message(
        self, conversation_source_id: str, content: str
    ) -> SendAttempt:
        self.send_calls.append((conversation_source_id, content))
        self._raise_injected("send_message")
        return self.next_send

    async def find_outbound_match(
        self,
        conversation_source_id: str,
        content_digest: str,
        earliest: datetime,
    ) -> SourceMessage | None:
        self.match_calls.append((conversation_source_id, content_digest, earliest))
        self._raise_injected("find_outbound_match")
        return self.outbound_match
