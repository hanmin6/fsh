from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(
    shutil.which("powershell.exe") is None,
    reason="Windows PowerShell is required for Windows installer contracts",
)

REPO_ROOT = Path(__file__).parents[2]


def run_script(name: str, *arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            "powershell.exe",
            "-NoProfile",
            "-NonInteractive",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(REPO_ROOT / "scripts" / name),
            *arguments,
        ],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def test_install_dry_run_plans_isolated_runtime(tmp_path: Path) -> None:
    result = run_script(
        "install-windows.ps1",
        "-InstallDir",
        str(tmp_path / "service"),
        "-AppDataDir",
        str(tmp_path / "data"),
        "-DryRun",
    )

    assert result.returncode == 0, result.stderr
    assert "python -m venv" in result.stdout
    assert "playwright install chromium" in result.stdout
    assert "MIC_APP_DATA_DIR" in result.stdout
    assert "api-key" not in result.stdout.casefold()


def test_install_rejects_source_tree_app_data() -> None:
    result = run_script(
        "install-windows.ps1",
        "-InstallDir",
        str(REPO_ROOT / ".runtime"),
        "-AppDataDir",
        str(REPO_ROOT / ".runtime" / "data"),
        "-DryRun",
    )

    assert result.returncode != 0
    assert "outside the source tree" in result.stderr


def test_scheduled_task_dry_run_is_interactive_and_binds_all_interfaces(
    tmp_path: Path,
) -> None:
    result = run_script(
        "register-task.ps1",
        "-InstallDir",
        str(tmp_path / "service"),
        "-DryRun",
    )

    assert result.returncode == 0, result.stderr
    assert "Interactive" in result.stdout
    assert "AtLogOn" in result.stdout
    assert "mic_gateway.main:create_production_app" in result.stdout
    assert "--host 0.0.0.0" in result.stdout
    assert "api-key" not in result.stdout.casefold()


def test_firewall_dry_run_requires_narrow_remote_addresses() -> None:
    missing = run_script("configure-firewall.ps1", "-DryRun")
    assert missing.returncode != 0

    broad = run_script(
        "configure-firewall.ps1",
        "-RemoteAddress",
        "0.0.0.0/0",
        "-DryRun",
    )
    assert broad.returncode != 0

    scoped = run_script(
        "configure-firewall.ps1",
        "-RemoteAddress",
        "127.0.0.1,192.168.1.0/24",
        "-DryRun",
    )
    assert scoped.returncode == 0, scoped.stderr
    assert "127.0.0.1" in scoped.stdout
    assert "192.168.1.0/24" in scoped.stdout
    assert "8787" in scoped.stdout
