from __future__ import annotations

from pathlib import Path

import pytest

from mic_gateway.config import Settings


def test_defaults_bind_to_all_interfaces(tmp_path: Path) -> None:
    settings = Settings(app_data_dir=tmp_path, _env_file=None)

    assert settings.host == "0.0.0.0"
    assert settings.port == 8787
    assert settings.conversation_sync_seconds == 30
    assert settings.order_sync_seconds == 300


def test_source_tree_cannot_be_runtime_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)

    with pytest.raises(ValueError, match="outside the source tree"):
        Settings(app_data_dir=tmp_path / "runtime")
