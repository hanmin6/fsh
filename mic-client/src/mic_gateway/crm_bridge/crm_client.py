from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any
from urllib.parse import quote


class CrmError(RuntimeError):
    """Base class for safe CRM bridge errors."""


class CrmAuthError(CrmError):
    """CRM rejected Agent credentials; callers should stop without retrying."""


class CrmPermanentError(CrmError):
    """CRM rejected a request that should not be retried unchanged."""


class CrmTransientError(CrmError):
    """CRM or transport failed transiently after bounded retries."""


_VERIFIED_RESPONSE = object()


@dataclass(frozen=True, slots=True, init=False)
class CrmSyncResult:
    """Sync response verified by CrmClient after a successful HTTP response."""

    request_id: str
    response: Mapping[str, Any]
    _verification: object

    def __init__(
        self,
        request_id: str,
        response: Mapping[str, Any],
        *,
        _verification: object,
    ) -> None:
        if _verification is not _VERIFIED_RESPONSE:
            raise ValueError("CrmSyncResult can only be created from a verified CRM response")
        object.__setattr__(self, "request_id", request_id)
        object.__setattr__(self, "response", MappingProxyType(dict(response)))
        object.__setattr__(self, "_verification", _verification)


class CrmClient:
    """Small authenticated CRM client with bounded retries and redacted errors."""

    def __init__(
        self,
        base_url: str,
        agent_key: str,
        agent_token: str | None = None,
        *,
        opener: Callable[..., Any] | None = None,
        max_retries: int = 2,
        backoff: Callable[[float], None] = time.sleep,
        timeout: float = 15,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.agent_key = agent_key
        self.agent_token = agent_token
        self.opener = opener or urllib.request.build_opener(_NoRedirectHandler()).open
        self.max_retries = max(0, min(max_retries, 5))
        self.backoff = backoff
        self.timeout = timeout

    def register(self, bootstrap_token: str, *, rotate: bool = True) -> str:
        data = self._request(
            "POST",
            "/Fusanhe/agent/register",
            request_id="mic-agent-register",
            payload={
                "agentKey": self.agent_key,
                "name": "Made-in-China Agent",
                "mode": "real",
                "capabilities": ["MadeInChina"],
                "rotateCredential": rotate,
            },
            bootstrap_token=bootstrap_token,
        )
        token = str(data.get("agentToken") or "")
        if not token:
            raise CrmPermanentError("CRM did not issue an Agent token")
        return token

    def sync_batch(self, payload: Mapping[str, Any], request_id: str) -> CrmSyncResult:
        response = self._request(
            "POST",
            "/Fusanhe/mic/sync",
            request_id=request_id,
            payload=payload,
            retryable=True,
        )
        if not _is_confirmed_sync_response(response, request_id):
            raise CrmPermanentError(f"CRM sync response was not confirmed; requestId={request_id}")
        return CrmSyncResult(
            request_id,
            response,
            _verification=_VERIFIED_RESPONSE,
        )

    def heartbeat(
        self,
        status: str = "online",
        last_error: str | None = None,
        request_id: str = "mic-heartbeat",
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {"agentKey": self.agent_key, "status": status}
        if last_error is not None:
            payload["lastError"] = last_error
        return self._request(
            "POST", "/Fusanhe/agent/heartbeat", request_id=request_id, payload=payload
        )

    def claim(self, request_id: str = "mic-claim") -> dict[str, Any]:
        return self._request(
            "POST",
            "/Fusanhe/agent/claim",
            request_id=request_id,
            payload={"agentKey": self.agent_key},
        )

    def mark_sending(self, task_id: str, request_id: str = "mic-sending") -> dict[str, Any]:
        return self._request(
            "POST",
            f"/Fusanhe/agent/task/{quote(task_id, safe='')}/sending",
            request_id=request_id,
            payload={"agentKey": self.agent_key},
        )

    def report_result(
        self,
        task_id: str,
        success: bool,
        platform_message_id: str | None = None,
        error_message: str | None = None,
        request_id: str = "mic-result",
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {"agentKey": self.agent_key, "success": success}
        if success and platform_message_id is not None:
            payload["platformMessageId"] = platform_message_id
        if not success and error_message is not None:
            payload["errorMessage"] = error_message
        return self._request(
            "POST",
            f"/Fusanhe/agent/task/{quote(task_id, safe='')}/result",
            request_id=request_id,
            payload=payload,
        )

    def _request(
        self,
        method: str,
        path: str,
        *,
        request_id: str,
        payload: Mapping[str, Any],
        bootstrap_token: str | None = None,
        retryable: bool = False,
    ) -> dict[str, Any]:
        headers = {"Content-Type": "application/json", "X-Request-Id": request_id}
        token = bootstrap_token or self.agent_token
        if token:
            headers.update(
                {
                    "X-Agent-Key": self.agent_key,
                    "X-Agent-Token": token,
                    "X-Automation-Token": token,
                }
            )
        body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        request = urllib.request.Request(
            self.base_url + path, data=body, headers=headers, method=method
        )
        for attempt in range(self.max_retries + 1):
            try:
                response = self.opener(request, timeout=self.timeout)
                status = int(getattr(response, "status", 200))
                raw = response.read()
            except urllib.error.HTTPError as exc:
                status, raw = exc.code, exc.read()
            except (TimeoutError, OSError, urllib.error.URLError):
                if retryable and attempt < self.max_retries:
                    self.backoff(min(0.25 * (2**attempt), 2.0))
                    continue
                raise CrmTransientError(f"CRM transport failed; requestId={request_id}") from None

            data = _json_object(raw)
            if status in (401, 403):
                raise CrmAuthError(f"CRM authentication failed; requestId={request_id}")
            if status == 429 or status >= 500:
                if retryable and attempt < self.max_retries:
                    self.backoff(min(0.25 * (2**attempt), 2.0))
                    continue
                raise CrmTransientError(f"CRM unavailable: HTTP {status}; requestId={request_id}")
            if status < 200 or status >= 300:
                raise CrmPermanentError(
                    f"CRM rejected request: HTTP {status}; requestId={request_id}"
                )
            if data is None:
                raise CrmTransientError(f"CRM returned invalid JSON; requestId={request_id}")
            return data
        raise AssertionError("bounded retry loop exhausted unexpectedly")


def _json_object(raw: bytes) -> dict[str, Any] | None:
    try:
        value = json.loads(raw)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None
    return value if isinstance(value, dict) else None


def _is_confirmed_sync_response(response: Mapping[str, Any], request_id: str) -> bool:
    if response.get("requestId") != request_id or response.get("accepted") is not True:
        return False
    if response.get("success") is False or response.get("completed") is False:
        return False
    if "error" in response:
        return False
    status = str(response.get("status", "")).lower()
    return status not in {"failed", "rejected", "error", "conflict"}


class _NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(
        self, req: Any, fp: Any, code: int, msg: str, headers: Any, newurl: str
    ) -> None:
        return None
