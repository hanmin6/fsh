from __future__ import annotations

import sqlite3
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest

from mic_gateway.crm_bridge.config import CrmBridgeConfig
from mic_gateway.crm_bridge.state import CrmBridgeState
from mic_gateway.crm_bridge.worker import (
    GatewayClientError,
    MicGatewayClient,
    MicOutboundWorker,
)


@pytest.fixture
def tmp_path(request: pytest.FixtureRequest) -> Path:
    path = Path.cwd() / ".outbound-test-tmp" / f"{request.node.name}-{uuid4().hex}"
    path.mkdir(parents=True)
    return path


class FakeCrm:
    def __init__(self, claim: dict[str, Any] | None) -> None:
        self.claim_response = claim or {"task": None, "paused": False}
        self.results: list[tuple[str, bool, str | None, str | None]] = []
        self.sending: list[str] = []
        self.heartbeats: list[tuple[str, str | None]] = []
        self.claim_calls = 0
        self.send_gate_error: Exception | None = None
        self.heartbeat_error: Exception | None = None

    def heartbeat(
        self,
        status: str = "online",
        last_error: str | None = None,
        request_id: str = "",
    ) -> dict[str, Any]:
        self.heartbeats.append((status, last_error))
        if self.heartbeat_error is not None:
            raise self.heartbeat_error
        return {"ok": True}

    def claim(self, request_id: str = "") -> dict[str, Any]:
        self.claim_calls += 1
        return self.claim_response

    def mark_sending(self, task_id: str, request_id: str = "") -> dict[str, Any]:
        self.sending.append(task_id)
        if self.send_gate_error is not None:
            raise self.send_gate_error
        return {"ok": True}

    def report_result(
        self,
        task_id: str,
        success: bool,
        platform_message_id: str | None = None,
        error_message: str | None = None,
        request_id: str = "",
    ) -> dict[str, Any]:
        self.results.append((task_id, success, platform_message_id, error_message))
        return {"ok": True}


class FakeGateway:
    def __init__(self) -> None:
        self.status_response = {
            "state": "healthy",
            "session": {"state": "healthy"},
            "sync": {
                "conversations": {
                    "fresh": True,
                    "failure_count": 0,
                    "last_error_code": None,
                    "paused_reason": None,
                }
            },
            "outbox": {"uncertain": 0},
        }
        self.conversations = [{"id": "gateway-uuid-1", "source_id": "mic-source-1"}]
        self.conversation_pages: dict[str | None, dict[str, Any]] | None = None
        self.conversation_page_calls: list[str | None] = []
        self.jobs: dict[str, dict[str, Any]] = {}
        self.submit_calls: list[tuple[str, dict[str, Any]]] = []
        self.before_poll: Any | None = None
        self.submit_error: Exception | None = None
        self.fail_after_submit = False
        self.next_job_id = "job-1"

    def status(self) -> dict[str, Any]:
        return self.status_response

    def list_conversations(self, limit: int = 200, cursor: str | None = None) -> dict[str, Any]:
        self.conversation_page_calls.append(cursor)
        if self.conversation_pages is not None:
            return self.conversation_pages[cursor]
        return {"items": self.conversations, "next_cursor": None}

    def submit_message(self, conversation_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        self.submit_calls.append((conversation_id, payload))
        if self.submit_error is not None:
            raise self.submit_error
        self.jobs.setdefault(self.next_job_id, {"id": self.next_job_id, "state": "queued"})
        if self.fail_after_submit:
            raise TimeoutError("simulated lost gateway response")
        return self.jobs[self.next_job_id]

    def get_job(self, job_id: str) -> dict[str, Any]:
        if self.before_poll is not None:
            self.before_poll(job_id)
        return self.jobs[job_id]


def approved_task(**updates: Any) -> dict[str, Any]:
    task = {
        "id": "crm-task-1",
        "channelType": "MadeInChina",
        "executionMode": "real",
        "inquiryId": "mic-source-1",
        "body": "Hello from the approved draft.",
    }
    task.update(updates)
    return task


def make_worker(tmp_path: Path, crm: FakeCrm, gateway: FakeGateway) -> MicOutboundWorker:
    return MicOutboundWorker(
        crm=crm,
        gateway=gateway,
        state=CrmBridgeState(tmp_path),
        poll_interval_seconds=0,
    )


def test_paused_claim_does_not_submit_or_report(tmp_path: Path) -> None:
    crm = FakeCrm({"task": None, "paused": True})
    gateway = FakeGateway()

    result = make_worker(tmp_path, crm, gateway).run_once()

    assert result.status == "paused"
    assert gateway.submit_calls == []
    assert crm.results == []


def test_wrong_channel_is_not_sent_to_gateway(tmp_path: Path) -> None:
    crm = FakeCrm({"task": approved_task(channelType="Alibaba"), "paused": False})
    gateway = FakeGateway()

    result = make_worker(tmp_path, crm, gateway).run_once()

    assert result.status == "rejected"
    assert result.action_required is True
    assert gateway.submit_calls == []
    assert crm.sending == []
    assert crm.results == []
    assert crm.heartbeats[-1][1] == "claimed_task_invalid"


@pytest.mark.parametrize(
    "updates",
    [
        {"executionMode": "mock"},
        {"body": "  "},
        {"inquiryId": ""},
        {"id": ""},
    ],
)
def test_non_real_or_incomplete_task_never_submits(tmp_path: Path, updates: dict[str, Any]) -> None:
    crm = FakeCrm({"task": approved_task(**updates), "paused": False})
    gateway = FakeGateway()

    result = make_worker(tmp_path, crm, gateway).run_once()

    assert result.status == "rejected"
    assert result.action_required is True
    assert gateway.submit_calls == []
    assert crm.heartbeats[-1][1] == "claimed_task_invalid"


@pytest.mark.parametrize("reason", ["human takeover", "cancelled task"])
def test_human_takeover_or_cancellation_at_sending_gate_blocks_gateway(
    tmp_path: Path, reason: str
) -> None:
    crm = FakeCrm({"task": approved_task(), "paused": False})
    crm.send_gate_error = RuntimeError(reason)
    gateway = FakeGateway()

    result = make_worker(tmp_path, crm, gateway).run_once()

    assert result.status == "blocked"
    assert gateway.submit_calls == []
    assert crm.results == []


def test_gateway_heartbeat_reports_service_health_before_claim(tmp_path: Path) -> None:
    crm = FakeCrm(None)
    gateway = FakeGateway()
    gateway.status_response = {"state": "operator_action_required"}

    make_worker(tmp_path, crm, gateway).run_once()

    assert crm.heartbeats[0][0] != "online"
    assert crm.claim_calls == 0
    assert gateway.submit_calls == []


def test_gateway_degraded_only_by_orders_still_allows_send(tmp_path: Path) -> None:
    crm = FakeCrm({"task": approved_task(), "paused": False})
    gateway = FakeGateway()
    gateway.status_response["state"] = "degraded"
    gateway.status_response["sync"]["orders"] = {
        "fresh": False,
        "failure_count": 1,
        "last_error_code": "stale_checkpoint",
        "paused_reason": None,
    }

    result = make_worker(tmp_path, crm, gateway).run_once()

    assert result.status == "pending"
    assert crm.claim_calls == 1
    assert len(gateway.submit_calls) == 1


@pytest.mark.parametrize(
    "change",
    [
        pytest.param(
            lambda status: status.update(state="operator_action_required"),
            id="operator-action",
        ),
        pytest.param(
            lambda status: status["session"].update(state="unhealthy"),
            id="session-unhealthy",
        ),
        pytest.param(
            lambda status: status["sync"]["conversations"].update(fresh=False),
            id="stale-conversations",
        ),
        pytest.param(
            lambda status: status["sync"]["conversations"].update(failure_count=1),
            id="conversation-failure",
        ),
        pytest.param(
            lambda status: status["sync"]["conversations"].update(paused_reason="manual_pause"),
            id="conversation-paused",
        ),
        pytest.param(lambda status: status["outbox"].update(uncertain=1), id="uncertain-outbox"),
        pytest.param(lambda status: status.pop("session"), id="missing-session"),
        pytest.param(lambda status: status.update(state=[]), id="malformed-overall-state"),
    ],
)
def test_gateway_without_explicit_send_safe_status_does_not_claim(
    tmp_path: Path, change: Any
) -> None:
    crm = FakeCrm({"task": approved_task(), "paused": False})
    gateway = FakeGateway()
    change(gateway.status_response)

    result = make_worker(tmp_path, crm, gateway).run_once()

    assert result.status == "gateway_not_ready"
    assert result.action_required is True
    assert crm.claim_calls == 0
    assert crm.sending == []
    assert crm.results == []
    assert gateway.submit_calls == []


def test_heartbeat_failure_blocks_claim_and_returns_safely(tmp_path: Path) -> None:
    crm = FakeCrm({"task": approved_task(), "paused": False})
    crm.heartbeat_error = RuntimeError("CRM heartbeat unavailable")
    gateway = FakeGateway()

    result = make_worker(tmp_path, crm, gateway).run_once()

    assert result.status == "heartbeat_failed"
    assert result.action_required is True
    assert crm.claim_calls == 0
    assert gateway.submit_calls == []


def test_gateway_unavailable_and_heartbeat_failure_return_safely(tmp_path: Path) -> None:
    crm = FakeCrm({"task": approved_task(), "paused": False})
    crm.heartbeat_error = RuntimeError("CRM heartbeat unavailable")
    gateway = FakeGateway()
    gateway.status = lambda: (_ for _ in ()).throw(TimeoutError("offline"))

    result = make_worker(tmp_path, crm, gateway).run_once()

    assert result.status == "heartbeat_failed"
    assert result.action_required is True
    assert crm.claim_calls == 0
    assert gateway.submit_calls == []


def test_uncertain_job_stays_pending_and_is_never_resubmitted(tmp_path: Path) -> None:
    crm = FakeCrm({"task": approved_task(), "paused": False})
    gateway = FakeGateway()
    gateway.jobs["job-1"] = {"id": "job-1", "state": "uncertain"}
    worker = make_worker(tmp_path, crm, gateway)

    first = worker.run_once()
    second = worker.run_once()

    assert first.status == "pending"
    assert second.status == "pending"
    assert len(gateway.submit_calls) == 1
    assert crm.results == []
    assert crm.claim_calls == 1


@pytest.mark.parametrize("state", ["queued", "sending", "requires_human_review"])
def test_nonterminal_gateway_states_remain_pending(tmp_path: Path, state: str) -> None:
    crm = FakeCrm({"task": approved_task(), "paused": False})
    gateway = FakeGateway()
    gateway.jobs["job-1"] = {"id": "job-1", "state": state}

    result = make_worker(tmp_path, crm, gateway).run_once()

    assert result.status == "pending"
    assert crm.results == []


def test_restart_resumes_persisted_gateway_job_before_claiming(tmp_path: Path) -> None:
    first_crm = FakeCrm({"task": approved_task(), "paused": False})
    gateway = FakeGateway()
    gateway.jobs["job-1"] = {"id": "job-1", "state": "sending"}
    first_worker = MicOutboundWorker(
        crm=first_crm,
        gateway=gateway,
        state=CrmBridgeState(tmp_path),
        poll_interval_seconds=0,
    )
    first_worker.run_once()

    resumed_crm = FakeCrm(None)
    gateway.jobs["job-1"] = {
        "id": "job-1",
        "state": "sent",
        "safe_result_metadata": {"source_message_id": "platform-msg-9"},
    }
    result = MicOutboundWorker(
        crm=resumed_crm,
        gateway=gateway,
        state=CrmBridgeState(tmp_path),
        poll_interval_seconds=0,
    ).run_once()

    assert result.status == "sent"
    assert resumed_crm.claim_calls == 0
    assert resumed_crm.results == [("crm-task-1", True, "platform-msg-9", None)]
    assert len(gateway.submit_calls) == 1


def test_lost_submit_response_is_durable_manual_reconciliation_without_body_or_resend(
    tmp_path: Path,
) -> None:
    crm = FakeCrm({"task": approved_task(), "paused": False})
    gateway = FakeGateway()
    gateway.fail_after_submit = True
    state = CrmBridgeState(tmp_path)
    worker = MicOutboundWorker(crm=crm, gateway=gateway, state=state, poll_interval_seconds=0)

    first = worker.run_once()
    gateway.fail_after_submit = False
    second = worker.run_once()

    assert first.status == "pending"
    assert second.status == "pending"
    assert second.action_required is True
    assert len(gateway.submit_calls) == 1
    assert crm.claim_calls == 1
    assert crm.results == []
    journal = state.outbound_jobs()[0]
    assert journal["gateway_job_id"] is None
    assert journal["idempotency_key"] == worker.idempotency_key("crm-task-1")
    with sqlite3.connect(state.path) as connection:
        columns = {row[1] for row in connection.execute("PRAGMA table_info(outbound_jobs)")}
        rows = connection.execute("SELECT * FROM outbound_jobs")
        stored = " ".join(str(cell) for row in rows for cell in row)
    assert "body" not in columns
    assert "Hello from the approved draft." not in stored


def test_sent_without_confirmed_source_message_id_is_not_crm_success(tmp_path: Path) -> None:
    crm = FakeCrm({"task": approved_task(), "paused": False})
    gateway = FakeGateway()
    gateway.jobs["job-1"] = {"id": "job-1", "state": "sent", "safe_result_metadata": {}}

    result = make_worker(tmp_path, crm, gateway).run_once()

    assert result.status == "pending"
    assert crm.results == []


def test_gateway_failure_reports_safe_crm_failure_code(tmp_path: Path) -> None:
    crm = FakeCrm({"task": approved_task(), "paused": False})
    gateway = FakeGateway()
    gateway.jobs["job-1"] = {"id": "job-1", "state": "failed", "failure_code": "validation_failed"}

    result = make_worker(tmp_path, crm, gateway).run_once()

    assert result.status == "failed"
    assert crm.results == [("crm-task-1", False, None, "mic_gateway_validation_failed")]


def test_duplicate_polls_keep_task_derived_idempotency_key(tmp_path: Path) -> None:
    crm = FakeCrm({"task": approved_task(), "paused": False})
    gateway = FakeGateway()
    worker = make_worker(tmp_path, crm, gateway)

    worker.run_once()
    worker.run_once()

    assert len(gateway.submit_calls) == 1
    body = gateway.submit_calls[0][1]
    assert body["intent"] == "greeting"
    assert body["idempotency_key"] == worker.idempotency_key("crm-task-1")


def test_gateway_job_id_is_persisted_before_first_poll(tmp_path: Path) -> None:
    crm = FakeCrm({"task": approved_task(), "paused": False})
    gateway = FakeGateway()
    state = CrmBridgeState(tmp_path)
    gateway.before_poll = lambda job_id: assert_journal_job_id(state, job_id)
    worker = MicOutboundWorker(crm=crm, gateway=gateway, state=state, poll_interval_seconds=0)

    worker.run_once()

    assert state.outbound_jobs()[0]["gateway_job_id"] == "job-1"


def test_crm_claim_without_task_is_idle(tmp_path: Path) -> None:
    crm = FakeCrm(None)
    gateway = FakeGateway()

    result = make_worker(tmp_path, crm, gateway).run_once()

    assert result.status == "idle"
    assert gateway.submit_calls == []


def test_source_resolution_failure_is_visible_and_lease_recoverable(tmp_path: Path) -> None:
    crm = FakeCrm({"task": approved_task(), "paused": False})
    gateway = FakeGateway()
    gateway.conversations = []

    result = make_worker(tmp_path, crm, gateway).run_once()

    assert result.status == "source_unavailable"
    assert result.task_id == "crm-task-1"
    assert result.action_required is True
    assert crm.sending == []
    assert crm.results == []
    assert crm.heartbeats[-1][1] == "source_conversation_unavailable"
    assert gateway.submit_calls == []


def test_repeated_conversation_cursor_stops_source_resolution(tmp_path: Path) -> None:
    crm = FakeCrm({"task": approved_task(), "paused": False})
    gateway = FakeGateway()
    gateway.conversation_pages = {
        None: {"items": [], "next_cursor": "repeat"},
        "repeat": {"items": [], "next_cursor": "repeat"},
    }

    result = make_worker(tmp_path, crm, gateway).run_once()

    assert result.status == "source_unavailable"
    assert result.action_required is True
    assert len(gateway.conversation_page_calls) == 2
    assert crm.sending == []
    assert gateway.submit_calls == []


def test_conversation_pagination_has_a_page_bound(tmp_path: Path) -> None:
    crm = FakeCrm({"task": approved_task(), "paused": False})
    gateway = FakeGateway()

    def always_next_page(limit: int = 200, cursor: str | None = None) -> dict[str, Any]:
        gateway.conversation_page_calls.append(cursor)
        return {"items": [], "next_cursor": f"page-{len(gateway.conversation_page_calls)}"}

    gateway.list_conversations = always_next_page
    result = make_worker(tmp_path, crm, gateway).run_once()

    assert result.status == "source_unavailable"
    assert result.action_required is True
    assert len(gateway.conversation_page_calls) == 100
    assert crm.sending == []
    assert gateway.submit_calls == []


def test_worker_startup_requires_dedicated_mic_send_key(tmp_path: Path) -> None:
    config = CrmBridgeConfig.from_env(
        {
            "MIC_APP_DATA_DIR": str(tmp_path),
            "MIC_CRM_READ_API_KEY": "synthetic-read-key",
            "MIC_CRM_AGENT_KEY": "agent",
            "MIC_ACCOUNT_HANDLE": "synthetic-account",
        }
    )

    with pytest.raises(ValueError, match="MIC gateway send API key is required"):
        MicOutboundWorker.from_config(
            config=config,
            crm=FakeCrm(None),
            state=CrmBridgeState(tmp_path),
        )


def test_worker_factory_uses_dedicated_send_key_not_read_key(tmp_path: Path) -> None:
    config = CrmBridgeConfig.from_env(
        {
            "MIC_APP_DATA_DIR": str(tmp_path),
            "MIC_CRM_READ_API_KEY": "synthetic-read-key",
            "MIC_CRM_SEND_API_KEY": "synthetic-send-key",
            "MIC_CRM_AGENT_KEY": "agent",
            "MIC_ACCOUNT_HANDLE": "synthetic-account",
            "MIC_CRM_AGENT_TOKEN": "synthetic-agent-token",
        }
    )

    worker = MicOutboundWorker.from_config(
        config=config, crm=FakeCrm(None), state=CrmBridgeState(tmp_path)
    )

    assert isinstance(worker.gateway, MicGatewayClient)
    assert worker.gateway.api_key == "synthetic-send-key"
    assert worker.gateway.api_key != config.mic_read_api_key


def test_worker_factory_requires_registered_crm_agent_token(tmp_path: Path) -> None:
    config = CrmBridgeConfig.from_env(
        {
            "MIC_APP_DATA_DIR": str(tmp_path),
            "MIC_CRM_READ_API_KEY": "synthetic-read-key",
            "MIC_CRM_SEND_API_KEY": "synthetic-send-key",
            "MIC_CRM_AGENT_KEY": "agent",
            "MIC_ACCOUNT_HANDLE": "synthetic-account",
        }
    )

    with pytest.raises(ValueError, match="CRM Agent token is required"):
        MicOutboundWorker.from_config(
            config=config,
            crm=FakeCrm(None),
            state=CrmBridgeState(tmp_path),
        )


def test_gateway_client_does_not_forward_send_key_after_redirect() -> None:
    target_hits: list[str | None] = []

    class TargetHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            target_hits.append(self.headers.get("X-API-Key"))
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b'{"state":"healthy"}')

        def log_message(self, format: str, *args: Any) -> None:
            return

    target = ThreadingHTTPServer(("127.0.0.1", 0), TargetHandler)
    target_thread = threading.Thread(target=target.serve_forever, daemon=True)
    target_thread.start()

    class RedirectHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            self.send_response(302)
            self.send_header("Location", f"http://127.0.0.1:{target.server_port}/capture")
            self.end_headers()

        def log_message(self, format: str, *args: Any) -> None:
            return

    origin = ThreadingHTTPServer(("127.0.0.1", 0), RedirectHandler)
    origin_thread = threading.Thread(target=origin.serve_forever, daemon=True)
    origin_thread.start()
    try:
        client = MicGatewayClient(f"http://127.0.0.1:{origin.server_port}", "synthetic-send-secret")
        with pytest.raises(GatewayClientError, match="HTTP 302"):
            client.status()
        assert target_hits == []
    finally:
        origin.shutdown()
        target.shutdown()
        origin.server_close()
        target.server_close()
        origin_thread.join(timeout=2)
        target_thread.join(timeout=2)


def assert_journal_job_id(state: CrmBridgeState, job_id: str) -> None:
    assert state.outbound_jobs()[0]["gateway_job_id"] == job_id
