from __future__ import annotations

import io
import json
import threading
import urllib.error
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

import pytest

from mic_gateway.crm_bridge.crm_client import (
    CrmAuthError,
    CrmClient,
    CrmPermanentError,
    CrmSyncResult,
    CrmTransientError,
)


class FakeResponse:
    def __init__(self, status: int, payload: dict[str, Any]) -> None:
        self.status = status
        self._body = json.dumps(payload).encode()

    def read(self) -> bytes:
        return self._body


def test_sync_uses_mic_route_and_stable_request_id() -> None:
    requests: list[Any] = []

    def opener(request: Any, timeout: float) -> FakeResponse:
        requests.append(request)
        return FakeResponse(200, {"requestId": "job-1:source-1:1", "accepted": True})

    client = CrmClient("http://127.0.0.1:8080", "agent", "token", opener=opener)
    result = client.sync_batch({"jobId": "job-1"}, "job-1:source-1:1")

    assert isinstance(result, CrmSyncResult)
    assert result.response["accepted"] is True
    assert requests[0].full_url == "http://127.0.0.1:8080/Fusanhe/mic/sync"
    assert requests[0].get_header("X-request-id") == "job-1:source-1:1"
    assert requests[0].get_header("X-agent-token") == "token"


def test_agent_routes_match_established_crm_contract() -> None:
    requests: list[Any] = []

    def opener(request: Any, timeout: float) -> FakeResponse:
        requests.append(request)
        return FakeResponse(200, {"ok": True})

    client = CrmClient("http://localhost:8080", "agent", "token", opener=opener)
    client.heartbeat(request_id="hb-1")
    client.claim(request_id="claim-1")
    client.mark_sending("task/1", request_id="send-1")
    client.report_result("task-1", True, "message-1", request_id="result-1")

    assert [request.full_url.rsplit("8080", 1)[1] for request in requests] == [
        "/Fusanhe/agent/heartbeat",
        "/Fusanhe/agent/claim",
        "/Fusanhe/agent/task/task%2F1/sending",
        "/Fusanhe/agent/task/task-1/result",
    ]


def test_register_requests_mic_capability_and_returns_token_once() -> None:
    captured: list[Any] = []

    def opener(request: Any, timeout: float) -> FakeResponse:
        captured.append(request)
        return FakeResponse(200, {"agentToken": "issued-once"})

    client = CrmClient("http://localhost:8080", "mic-agent", opener=opener)
    token = client.register("bootstrap-secret", rotate=True)
    payload = json.loads(captured[0].data)
    assert payload["capabilities"] == ["MadeInChina"]
    assert captured[0].get_header("X-automation-token") == "bootstrap-secret"
    assert token == "issued-once"
    assert client.agent_token is None


def test_auth_errors_stop_without_retry_and_do_not_echo_secrets() -> None:
    calls = 0

    def opener(request: Any, timeout: float) -> FakeResponse:
        nonlocal calls
        calls += 1
        return FakeResponse(401, {"error": "synthetic-secret-token"})

    client = CrmClient("http://localhost", "agent", "synthetic-secret-token", opener=opener)
    with pytest.raises(CrmAuthError) as error:
        client.claim()
    assert calls == 1
    assert "synthetic-secret-token" not in str(error.value)


@pytest.mark.parametrize("status", [429, 500, 503])
def test_sync_transient_statuses_retry_with_a_bound(status: int) -> None:
    calls = 0
    delays: list[float] = []

    def opener(request: Any, timeout: float) -> FakeResponse:
        nonlocal calls
        calls += 1
        return FakeResponse(status, {"error": "temporary"})

    client = CrmClient(
        "http://localhost", "agent", "token", opener=opener, max_retries=1, backoff=delays.append
    )
    with pytest.raises(CrmTransientError):
        client.sync_batch({"jobId": "synthetic-job"}, "synthetic-request")
    assert calls == 2
    assert delays == [0.25]


def test_permanent_4xx_is_not_retried() -> None:
    calls = 0

    def opener(request: Any, timeout: float) -> FakeResponse:
        nonlocal calls
        calls += 1
        return FakeResponse(409, {"code": "request_conflict"})

    client = CrmClient("http://localhost", "agent", "token", opener=opener)
    with pytest.raises(CrmPermanentError, match="HTTP 409"):
        client.claim()
    assert calls == 1


@pytest.mark.parametrize("operation", ["register", "claim"])
def test_non_idempotent_agent_operations_do_not_retry(operation: str) -> None:
    calls = 0

    def opener(request: Any, timeout: float) -> FakeResponse:
        nonlocal calls
        calls += 1
        return FakeResponse(503, {"error": "temporary"})

    client = CrmClient("http://localhost", "agent", "token", opener=opener, max_retries=3)
    with pytest.raises(CrmTransientError):
        if operation == "register":
            client.register("bootstrap-token", rotate=True)
        else:
            client.claim()
    assert calls == 1


def test_sync_timeout_after_commit_retries_with_same_request_id_and_payload() -> None:
    requests: list[tuple[str, bytes]] = []

    def opener(request: Any, timeout: float) -> FakeResponse:
        requests.append((request.get_header("X-request-id"), request.data))
        if len(requests) == 1:
            raise TimeoutError("simulated lost response after commit")
        return FakeResponse(
            200,
            {"requestId": "stable-request", "accepted": True},
        )

    client = CrmClient(
        "http://localhost", "agent", "token", opener=opener, max_retries=1, backoff=lambda _: None
    )
    result = client.sync_batch({"jobId": "stable-job", "batchNo": 1}, "stable-request")

    assert result.request_id == "stable-request"
    assert requests == [
        ("stable-request", b'{"jobId":"stable-job","batchNo":1}'),
        ("stable-request", b'{"jobId":"stable-job","batchNo":1}'),
    ]


def test_http_error_status_is_classified() -> None:
    def opener(request: Any, timeout: float) -> FakeResponse:
        raise urllib.error.HTTPError(
            request.full_url, 403, "forbidden", {}, io.BytesIO(b'{"error":"denied"}')
        )

    client = CrmClient("http://localhost", "agent", "token", opener=opener)
    with pytest.raises(CrmAuthError):
        client.claim()


def test_untrusted_error_body_is_not_copied_into_exception() -> None:
    echoed_secret = "synthetic-secret-echoed-by-crm"

    def opener(request: Any, timeout: float) -> FakeResponse:
        return FakeResponse(400, {"code": echoed_secret, "error": echoed_secret})

    client = CrmClient("http://localhost", "agent", "token", opener=opener)
    with pytest.raises(CrmPermanentError) as error:
        client.claim()
    assert echoed_secret not in str(error.value)
    assert "HTTP 400" in str(error.value)


def test_authenticated_crm_request_does_not_follow_cross_origin_redirect() -> None:
    target_hits: list[str | None] = []

    class TargetHandler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            target_hits.append(self.headers.get("X-Agent-Token"))
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b'{"ok":true}')

        def log_message(self, format: str, *args: Any) -> None:
            return

    target = ThreadingHTTPServer(("127.0.0.1", 0), TargetHandler)
    target_thread = threading.Thread(target=target.serve_forever, daemon=True)
    target_thread.start()

    class RedirectHandler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            self.send_response(302)
            self.send_header(
                "Location", f"http://127.0.0.1:{target.server_port}/capture"
            )
            self.end_headers()

        def log_message(self, format: str, *args: Any) -> None:
            return

    origin = ThreadingHTTPServer(("127.0.0.1", 0), RedirectHandler)
    origin_thread = threading.Thread(target=origin.serve_forever, daemon=True)
    origin_thread.start()
    try:
        client = CrmClient(
            f"http://127.0.0.1:{origin.server_port}",
            "agent",
            "synthetic-agent-secret",
            timeout=3,
        )
        with pytest.raises(CrmPermanentError, match="HTTP 302"):
            client.claim()
        assert target_hits == []
    finally:
        origin.shutdown()
        target.shutdown()
        origin.server_close()
        target.server_close()
        origin_thread.join(timeout=2)
        target_thread.join(timeout=2)
