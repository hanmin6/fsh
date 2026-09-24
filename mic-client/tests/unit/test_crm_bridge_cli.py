from __future__ import annotations

from io import StringIO
from pathlib import Path
from typing import Any

from mic_gateway.crm_bridge.cli import run_cli
from mic_gateway.crm_bridge.config import CrmBridgeConfig
from mic_gateway.crm_bridge.state import CrmBridgeState


class FakeCrm:
    def __init__(self) -> None:
        self.register_calls: list[tuple[str, bool]] = []

    def register(self, bootstrap_token: str, *, rotate: bool = True) -> str:
        self.register_calls.append((bootstrap_token, rotate))
        return "one-time-issued-token"


class FakeGateway:
    def status(self) -> dict[str, Any]:
        return {"state": "healthy"}


def _config(tmp_path: Path) -> CrmBridgeConfig:
    return CrmBridgeConfig(
        app_data_dir=tmp_path,
        mic_base_url="http://127.0.0.1:8787",
        mic_read_api_key="read-secret",
        crm_base_url="http://127.0.0.1:8080",
        crm_agent_key="mic-agent",
        account_handle="synthetic-account",
        crm_bootstrap_token="bootstrap-secret",
        crm_agent_token="synthetic-agent-token",
    )


def test_register_prints_new_token_once_and_does_not_store_it(tmp_path: Path) -> None:
    crm = FakeCrm()
    output = StringIO()

    code = run_cli(["register"], config=_config(tmp_path), crm=crm, output=output)

    assert code == 0
    assert crm.register_calls == [("bootstrap-secret", True)]
    assert output.getvalue().strip() == "one-time-issued-token"
    assert "one-time-issued-token" not in CrmBridgeState(tmp_path).path.read_bytes().decode(
        errors="ignore"
    )


def test_status_reports_progress_without_credentials(tmp_path: Path) -> None:
    output = StringIO()
    state = CrmBridgeState(tmp_path)
    state.stage_batch(
        "conversations",
        start_cursor=None,
        next_cursor="next",
        request_id="job:1",
        payload={"safe": True},
    )

    code = run_cli(["status"], config=_config(tmp_path), state=state, output=output)

    assert code == 0
    assert "conversations" in output.getvalue()
    assert "read-secret" not in output.getvalue()
    assert "bootstrap-secret" not in output.getvalue()


def test_daemon_interval_is_validated_before_start(tmp_path: Path) -> None:
    output = StringIO()

    code = run_cli(["daemon", "--interval", "0"], config=_config(tmp_path), output=output)

    assert code != 0
    assert "interval" in output.getvalue().lower()


class ImportGateway:
    def __init__(self) -> None:
        self.calls = 0

    def list_conversations(self, limit: int = 200, cursor: str | None = None) -> dict[str, Any]:
        self.calls += 1
        return {"items": [], "next_cursor": None}

    def list_messages(
        self, conversation_id: str, limit: int = 200, cursor: str | None = None
    ) -> dict[str, Any]:
        return {"items": [], "next_cursor": None}


class SyncCrm(FakeCrm):
    def sync_batch(self, payload: dict[str, Any], request_id: str) -> Any:
        from mic_gateway.crm_bridge.crm_client import CrmClient

        return CrmClient(
            "http://localhost",
            "agent",
            "token",
            opener=lambda request, timeout: _Response({"requestId": request_id, "accepted": True}),
        ).sync_batch(payload, request_id)


class _Response:
    status = 200

    def __init__(self, payload: dict[str, Any]) -> None:
        import json

        self.body = json.dumps(payload).encode()

    def read(self) -> bytes:
        return self.body


def test_once_dispatches_read_only_import(tmp_path: Path) -> None:
    gateway = ImportGateway()
    output = StringIO()

    code = run_cli(
        ["once"],
        config=_config(tmp_path),
        gateway=gateway,
        crm=SyncCrm(),
        state=CrmBridgeState(tmp_path),
        output=output,
    )

    assert code == 0
    assert gateway.calls == 1
    assert '"mode": "once"' in output.getvalue()


def test_daemon_repeats_once_at_configured_interval(tmp_path: Path) -> None:
    gateway = ImportGateway()
    delays: list[float] = []

    code = run_cli(
        ["daemon", "--interval", "0.5"],
        config=_config(tmp_path),
        gateway=gateway,
        crm=SyncCrm(),
        state=CrmBridgeState(tmp_path),
        output=StringIO(),
        sleeper=delays.append,
        max_iterations=2,
    )

    assert code == 0
    assert gateway.calls == 2
    assert delays == [0.5]


def test_backfill_dispatches_and_persists_completion(tmp_path: Path) -> None:
    gateway = ImportGateway()
    state = CrmBridgeState(tmp_path)

    code = run_cli(
        ["backfill"],
        config=_config(tmp_path),
        gateway=gateway,
        crm=SyncCrm(),
        state=state,
        output=StringIO(),
    )

    assert code == 0
    assert gateway.calls == 1


class FailingGateway:
    def list_conversations(self, limit: int = 200, cursor: str | None = None) -> dict[str, Any]:
        return {
            "items": [
                {
                    "id": "gateway-id",
                    "source_id": "source-id",
                    "buyer_reference": "buyer-id",
                    "history_complete": True,
                    "inquiry_subject": "inquiry",
                    "unread": False,
                }
            ],
            "next_cursor": None,
        }

    def list_messages(
        self, conversation_id: str, limit: int = 200, cursor: str | None = None
    ) -> dict[str, Any]:
        return {"items": [], "next_cursor": None}


class AuthFailingCrm:
    def sync_batch(self, payload: dict[str, Any], request_id: str) -> Any:
        from mic_gateway.crm_bridge.crm_client import CrmAuthError

        raise CrmAuthError("synthetic-secret-token")


def test_failure_returns_safe_code_without_exception_secret(tmp_path: Path) -> None:
    output = StringIO()

    code = run_cli(
        ["once"],
        config=_config(tmp_path),
        gateway=FailingGateway(),
        crm=AuthFailingCrm(),
        state=CrmBridgeState(tmp_path),
        output=output,
    )

    assert code == 1
    assert "crm_auth" in output.getvalue()
    assert "synthetic-secret-token" not in output.getvalue()


class TransientThenSuccessCrm:
    def __init__(self) -> None:
        self.request_ids: list[str] = []

    def sync_batch(self, payload: dict[str, Any], request_id: str) -> Any:
        from mic_gateway.crm_bridge.crm_client import CrmClient, CrmTransientError

        self.request_ids.append(request_id)
        if len(self.request_ids) == 1:
            raise CrmTransientError("synthetic-secret-token")
        return CrmClient(
            "http://localhost",
            "agent",
            "token",
            opener=lambda request, timeout: _Response({"requestId": request_id, "accepted": True}),
        ).sync_batch(payload, request_id)


def test_daemon_retries_transient_failure_without_losing_checkpoint(tmp_path: Path) -> None:
    gateway = FailingGateway()
    crm = TransientThenSuccessCrm()
    state = CrmBridgeState(tmp_path)
    output = StringIO()
    delays: list[float] = []

    code = run_cli(
        ["daemon", "--interval", "0.5"],
        config=_config(tmp_path),
        gateway=gateway,
        crm=crm,
        state=state,
        output=output,
        sleeper=delays.append,
        max_iterations=2,
    )

    assert code == 0
    assert len(crm.request_ids) == 2
    assert crm.request_ids[0] == crm.request_ids[1]
    assert state.checkpoint("conversations:once") == "__mic_import_complete__"
    assert state.pending_batch("conversations:once") is None
    assert delays == [1.0]
    assert '"status": "retrying"' in output.getvalue()
    assert '"error": "crm_unavailable"' in output.getvalue()
    assert "synthetic-secret-token" not in output.getvalue()


def test_daemon_interval_must_stay_within_bounds(tmp_path: Path) -> None:
    for interval in ("0.01", "3601", "nan", "inf"):
        output = StringIO()
        code = run_cli(
            ["daemon", "--interval", interval],
            config=_config(tmp_path),
            output=output,
        )
        assert code == 2
        assert "interval" in output.getvalue().lower()


def test_daemon_stops_on_auth_failure_without_retry_or_backoff(tmp_path: Path) -> None:
    output = StringIO()
    delays: list[float] = []

    code = run_cli(
        ["daemon", "--interval", "0.5"],
        config=_config(tmp_path),
        gateway=FailingGateway(),
        crm=AuthFailingCrm(),
        state=CrmBridgeState(tmp_path),
        output=output,
        sleeper=delays.append,
        max_iterations=4,
    )

    assert code == 1
    assert delays == []
    assert "crm_auth" in output.getvalue()
    assert "synthetic-secret-token" not in output.getvalue()


def test_status_surfaces_pending_batch_conflict_action_code(tmp_path: Path) -> None:
    state = CrmBridgeState(tmp_path)
    state.stage_batch(
        "conversations:once",
        start_cursor=None,
        next_cursor="next",
        request_id="safe-request-id",
        payload={"body": "private synthetic buyer text"},
    )
    state.mark_pending_conflict("conversations:once", "safe-request-id")
    output = StringIO()

    code = run_cli(["status"], config=_config(tmp_path), state=state, output=output)

    assert code == 0
    assert "pending_batch_conflict" in output.getvalue()
    assert "safe-request-id" in output.getvalue()
    assert "private synthetic buyer text" not in output.getvalue()


def test_operator_can_advance_only_after_explicit_verified_acceptance(tmp_path: Path) -> None:
    state = CrmBridgeState(tmp_path)
    state.stage_batch(
        "conversations:once",
        start_cursor=None,
        next_cursor="next",
        request_id="verified-request-id",
        payload={"safe": True},
    )
    state.mark_pending_conflict("conversations:once", "verified-request-id")
    output = StringIO()

    code = run_cli(
        [
            "resolve-pending",
            "conversations:once",
            "--request-id",
            "verified-request-id",
            "--verified-accepted",
        ],
        config=_config(tmp_path),
        state=state,
        output=output,
    )

    assert code == 0
    assert state.checkpoint("conversations:once") == "next"
    assert state.pending_batch("conversations:once") is None
    assert "verified_acceptance_confirmed" in output.getvalue().lower()


def test_operator_can_clear_pending_after_verifying_not_accepted(tmp_path: Path) -> None:
    state = CrmBridgeState(tmp_path)
    state.stage_batch(
        "conversations:once",
        start_cursor=None,
        next_cursor="next",
        request_id="rejected-request-id",
        payload={"safe": True},
    )
    state.mark_pending_conflict("conversations:once", "rejected-request-id")
    output = StringIO()

    code = run_cli(
        [
            "resolve-pending",
            "conversations:once",
            "--request-id",
            "rejected-request-id",
            "--verified-not-accepted",
        ],
        config=_config(tmp_path),
        state=state,
        output=output,
    )

    assert code == 0
    assert state.checkpoint("conversations:once") is None
    assert state.pending_batch("conversations:once") is None
    assert "without_advance" in output.getvalue()


def test_operator_resolution_rejects_wrong_request_id_without_mutation(tmp_path: Path) -> None:
    state = CrmBridgeState(tmp_path)
    state.stage_batch(
        "conversations:once",
        start_cursor=None,
        next_cursor="next",
        request_id="expected-request-id",
        payload={"safe": True},
    )
    state.mark_pending_conflict("conversations:once", "expected-request-id")
    output = StringIO()

    code = run_cli(
        [
            "resolve-pending",
            "conversations:once",
            "--request-id",
            "wrong-request-id",
            "--verified-accepted",
        ],
        config=_config(tmp_path),
        state=state,
        output=output,
    )

    assert code == 2
    assert state.checkpoint("conversations:once") is None
    pending = state.pending_batch("conversations:once")
    assert pending is not None
    assert pending["request_id"] == "expected-request-id"
    assert "AutomationAudit" in output.getvalue()
