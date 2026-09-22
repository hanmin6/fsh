import subprocess
import sys

def test_runner_help_command():
    res = subprocess.run(
        [sys.executable, "-m", "alibaba_messenger.run_server", "--help"],
        capture_output=True,
        text=True,
        errors="replace"
    )
    assert res.returncode == 0
    assert res.stdout is not None
    assert "usage" in res.stdout.lower()
    assert "--headless" in res.stdout
    assert "--port" in res.stdout


def test_sync_runner_help_command_has_backfill_and_status_without_browser():
    res = subprocess.run(
        [sys.executable, "-m", "alibaba_messenger.run_sync", "--help"],
        capture_output=True, text=True, errors="replace"
    )
    assert res.returncode == 0
    assert "backfill" in res.stdout
    assert "status" in res.stdout
    assert "once" in res.stdout
    assert "daemon" in res.stdout
    assert "--interval" in res.stdout
    assert "--headless" in res.stdout
