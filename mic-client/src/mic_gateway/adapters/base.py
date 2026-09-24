from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Protocol, runtime_checkable

from mic_gateway.domain import SourceConversation, SourceMessage, SourceOrder


@dataclass(frozen=True, slots=True)
class SourceCheckpoint:
    cursor: str | None
    updated_after: datetime | None

    def __post_init__(self) -> None:
        if self.updated_after is not None and (
            self.updated_after.tzinfo is None or self.updated_after.utcoffset() is None
        ):
            raise ValueError("updated_after must be timezone-aware")


@dataclass(frozen=True, slots=True)
class SourcePage[T]:
    items: tuple[T, ...]
    next_cursor: str | None
    history_complete: bool = False
    buyer_name: str | None = None
    country: str | None = None
    buyer_id: str | None = None

    def __post_init__(self) -> None:
        if self.history_complete and self.next_cursor is not None:
            raise ValueError("history_complete requires next_cursor to be None")


class SessionState(StrEnum):
    HEALTHY = "healthy"
    AUTHENTICATION_REQUIRED = "authentication_required"
    VERIFICATION_REQUIRED = "verification_required"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True, slots=True)
class SessionHealth:
    state: SessionState
    detail_code: str | None = None

    @property
    def healthy(self) -> bool:
        return self.state is SessionState.HEALTHY

    @property
    def requires_operator(self) -> bool:
        return self.state in {
            SessionState.AUTHENTICATION_REQUIRED,
            SessionState.VERIFICATION_REQUIRED,
        }

    @classmethod
    def available(cls) -> SessionHealth:
        return cls(SessionState.HEALTHY)

    @classmethod
    def authentication_required(
        cls, detail_code: str = "authentication_required"
    ) -> SessionHealth:
        return cls(SessionState.AUTHENTICATION_REQUIRED, detail_code)

    @classmethod
    def verification_required(
        cls, detail_code: str = "verification_required"
    ) -> SessionHealth:
        return cls(SessionState.VERIFICATION_REQUIRED, detail_code)

    @classmethod
    def unavailable(cls, detail_code: str = "browser_unavailable") -> SessionHealth:
        return cls(SessionState.UNAVAILABLE, detail_code)


class SendOutcome(StrEnum):
    SENT = "sent"
    TRANSIENT_FAILURE = "transient_failure"
    PERMANENT_FAILURE = "permanent_failure"
    UNCERTAIN = "uncertain"


@dataclass(frozen=True, slots=True)
class SendAttempt:
    outcome: SendOutcome
    code: str | None = None
    source_message_id: str | None = None

    @classmethod
    def sent(cls, source_message_id: str | None = None) -> SendAttempt:
        return cls(SendOutcome.SENT, source_message_id=source_message_id)

    @classmethod
    def transient_failure(cls, code: str) -> SendAttempt:
        return cls(SendOutcome.TRANSIENT_FAILURE, code=code)

    @classmethod
    def permanent_failure(cls, code: str) -> SendAttempt:
        return cls(SendOutcome.PERMANENT_FAILURE, code=code)

    @classmethod
    def uncertain(cls, code: str) -> SendAttempt:
        return cls(SendOutcome.UNCERTAIN, code=code)


@runtime_checkable
class SiteAdapter(Protocol):
    async def check_session(self) -> SessionHealth: ...

    async def list_orders(
        self, checkpoint: SourceCheckpoint
    ) -> SourcePage[SourceOrder]: ...

    async def list_conversations(
        self, checkpoint: SourceCheckpoint
    ) -> SourcePage[SourceConversation]: ...

    async def list_messages(
        self,
        conversation_source_id: str,
        checkpoint: SourceCheckpoint,
    ) -> SourcePage[SourceMessage]: ...

    async def send_message(
        self, conversation_source_id: str, content: str
    ) -> SendAttempt: ...

    async def find_outbound_match(
        self,
        conversation_source_id: str,
        content_digest: str,
        earliest: datetime,
    ) -> SourceMessage | None: ...
