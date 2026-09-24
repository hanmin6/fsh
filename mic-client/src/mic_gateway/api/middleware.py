from __future__ import annotations

import asyncio
import re
import time
from collections import defaultdict, deque
from collections.abc import Callable
from typing import Any
from uuid import uuid4

from fastapi import Request
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from mic_gateway.api.auth import Principal
from mic_gateway.errors import ApiError

REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9._-]{1,64}$")


def normalize_request_id(value: str | None) -> str:
    if value is not None and REQUEST_ID_PATTERN.fullmatch(value):
        return value
    return str(uuid4())


class RequestContextMiddleware:
    def __init__(self, app: ASGIApp, max_request_bytes: int) -> None:
        self.app = app
        self.max_request_bytes = max_request_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = {key.lower(): value for key, value in scope.get("headers", [])}
        raw_request_id = headers.get(b"x-request-id")
        request_id = normalize_request_id(
            raw_request_id.decode("ascii", errors="ignore") if raw_request_id else None
        )
        state = scope.setdefault("state", {})
        state["request_id"] = request_id

        raw_content_length = headers.get(b"content-length")
        if raw_content_length is not None:
            try:
                if int(raw_content_length) > self.max_request_bytes:
                    await self._send_too_large(scope, receive, send, request_id)
                    return
            except ValueError:
                await self._send_too_large(scope, receive, send, request_id)
                return

        buffered: list[Message] = []
        total = 0
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            body = message.get("body", b"")
            total += len(body)
            if total > self.max_request_bytes:
                await self._send_too_large(scope, receive, send, request_id)
                return
            buffered.append(message)
            if not message.get("more_body", False):
                break

        position = 0

        async def replay_receive() -> Message:
            nonlocal position
            if position < len(buffered):
                message = buffered[position]
                position += 1
                return message
            return {"type": "http.request", "body": b"", "more_body": False}

        async def add_request_id_header(message: Message) -> None:
            if message["type"] == "http.response.start":
                response_headers = [
                    header
                    for header in message.get("headers", [])
                    if header[0].lower() != b"x-request-id"
                ]
                response_headers.append((b"x-request-id", request_id.encode("ascii")))
                message["headers"] = response_headers
            await send(message)

        await self.app(scope, replay_receive, add_request_id_header)

    async def _send_too_large(
        self, scope: Scope, receive: Receive, send: Send, request_id: str
    ) -> None:
        response = JSONResponse(
            status_code=413,
            content={
                "error": {
                    "code": "request_too_large",
                    "message": "The request body exceeds the configured limit",
                    "request_id": request_id,
                }
            },
            headers={"X-Request-ID": request_id},
        )
        await response(scope, receive, send)


class RateLimiter:
    def __init__(self, clock: Callable[[], float] = time.monotonic) -> None:
        self._clock = clock
        self._events: defaultdict[str, deque[float]] = defaultdict(deque)
        self._lock = asyncio.Lock()

    async def consume(self, key: str, *, limit: int, window_seconds: int) -> bool:
        now = self._clock()
        cutoff = now - window_seconds
        async with self._lock:
            events = self._events[key]
            while events and events[0] <= cutoff:
                events.popleft()
            if len(events) >= limit:
                return False
            events.append(now)
            return True


async def enforce_rate_limit(
    request: Request,
    principal: Principal,
    *,
    bucket: str,
    limit: int,
    window_seconds: int,
) -> None:
    limiter: RateLimiter = request.app.state.rate_limiter
    allowed = await limiter.consume(
        f"{principal.key_id}:{bucket}", limit=limit, window_seconds=window_seconds
    )
    if not allowed:
        raise ApiError(429, "rate_limited", "Too many requests")


def safe_error_payload(error: ApiError, request_id: str) -> dict[str, dict[str, Any]]:
    return {
        "error": {
            "code": error.code,
            "message": error.message,
            "request_id": request_id,
        }
    }
