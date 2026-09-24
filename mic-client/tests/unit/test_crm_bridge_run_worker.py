from __future__ import annotations

from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest

from mic_gateway.crm_bridge import run_worker
from mic_gateway.crm_bridge.worker import WorkerResult


@pytest.fixture
def tmp_path(request: pytest.FixtureRequest) -> Path:
    path = Path.cwd() / ".run-worker-test-tmp" / f"{request.node.name}-{uuid4().hex}"
    path.mkdir(parents=True)
    return path


class FakeWorker:
    def __init__(self, outcomes: list[WorkerResult | Exception]) -> None:
        self.outcomes = list(outcomes)
        self.calls = 0

    def run_once(self) -> WorkerResult:
        self.calls += 1
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


def _set_valid_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    values = {
        "MIC_APP_DATA_DIR": str(tmp_path),
        "MIC_CRM_READ_API_KEY": "synthetic-read-key",
        "MIC_CRM_SEND_API_KEY": "synthetic-send-secret",
        "MIC_CRM_AGENT_KEY": "synthetic-agent-key",
        "MIC_CRM_AGENT_TOKEN": "synthetic-agent-secret",
    }
    for name, value in values.items():
        monkeypatch.setenv(name, value)


def test_worker_cli_fails_startup_without_send_key(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _set_valid_env(monkeypatch, tmp_path)
    monkeypatch.delenv("MIC_CRM_SEND_API_KEY")

    result = run_worker.main(["--once"])

    assert result == 2
    captured = capsys.readouterr()
    output = captured.out + captured.err
    assert "synthetic" not in output
    assert "startup failed" in output


def test_worker_cli_fails_without_registered_crm_agent_token(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _set_valid_env(monkeypatch, tmp_path)
    monkeypatch.delenv("MIC_CRM_AGENT_TOKEN")

    result = run_worker.main(["--once"])

    captured = capsys.readouterr()
    assert result == 2
    assert "synthetic" not in captured.out + captured.err
    assert "startup failed" in captured.err


@pytest.mark.parametrize("status", ["paused", "idle"])
def test_once_mode_reports_safe_status_without_leaking_secrets(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    status: str,
) -> None:
    monkeypatch.setattr(
        run_worker.CrmBridgeConfig,
        "from_env",
        classmethod(lambda cls: object()),
    )
    fake = FakeWorker([WorkerResult(status)])
    monkeypatch.setattr(run_worker, "_build_worker", lambda config: fake)

    result = run_worker.main(["--once"])

    captured = capsys.readouterr()
    assert result == 0
    assert fake.calls == 1
    assert f"status={status}" in captured.out
    assert "synthetic" not in captured.out + captured.err


def test_once_mode_returns_nonzero_for_blocked_action_required_result(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(
        run_worker.CrmBridgeConfig,
        "from_env",
        classmethod(lambda cls: object()),
    )
    fake = FakeWorker([WorkerResult("blocked", action_required=True)])
    monkeypatch.setattr(run_worker, "_build_worker", lambda config: fake)

    result = run_worker.main(["--once"])

    captured = capsys.readouterr()
    assert result == 1
    assert fake.calls == 1
    assert "status=blocked" in captured.out


def test_loop_uses_bounded_exponential_backoff_and_redacts_exception(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    fake = FakeWorker(
        [
            WorkerResult("gateway_unavailable", action_required=True),
            RuntimeError("synthetic-send-secret leaked body"),
            WorkerResult("idle"),
        ]
    )
    delays: list[float] = []

    result = run_worker.run_loop(
        fake,
        interval_seconds=2,
        once=False,
        sleeper=delays.append,
        max_iterations=3,
    )

    captured = capsys.readouterr()
    assert result == 0
    assert fake.calls == 3
    assert delays == [2, 4]
    assert "synthetic" not in captured.out + captured.err
    assert "iteration failed" in captured.err


def test_interval_is_bounded() -> None:
    with pytest.raises(SystemExit):
        run_worker.main(["--interval", "3601", "--once"])


def test_keyboard_interrupt_stops_cleanly(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(
        run_worker.CrmBridgeConfig,
        "from_env",
        classmethod(lambda cls: object()),
    )
    fake = FakeWorker([WorkerResult("idle")])
    monkeypatch.setattr(run_worker, "_build_worker", lambda config: fake)

    def interrupt_loop(worker: FakeWorker, **kwargs: Any) -> int:
        worker.run_once()
        raise KeyboardInterrupt

    monkeypatch.setattr(run_worker, "run_loop", interrupt_loop)

    result = run_worker.main(["--interval", "1"])

    captured = capsys.readouterr()
    assert result == 0
    assert fake.calls == 1
    assert "stopped" in captured.out

