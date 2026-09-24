from __future__ import annotations

from pathlib import Path

import pytest

from mic_gateway.crm_bridge.config import CrmBridgeConfig, CrmBridgeConfigError


def _env(tmp_path: Path, **updates: str) -> dict[str, str]:
    return {
        "MIC_APP_DATA_DIR": str(tmp_path),
        "MIC_CRM_READ_API_KEY": "synthetic-read-key",
        "MIC_CRM_AGENT_KEY": "synthetic-agent",
        "MIC_ACCOUNT_HANDLE": "synthetic-account",
        **updates,
    }


def test_defaults_are_loopback_and_credentials_are_separate(tmp_path: Path) -> None:
    config = CrmBridgeConfig.from_env(_env(tmp_path, MIC_CRM_AGENT_TOKEN="synthetic-agent-token"))

    assert config.mic_base_url == "http://127.0.0.1:8787"
    assert config.crm_base_url == "http://127.0.0.1:8080"
    assert config.mic_read_api_key == "synthetic-read-key"
    assert config.mic_send_api_key is None
    assert config.crm_agent_token == "synthetic-agent-token"
    assert "synthetic-read-key" not in repr(config)
    assert "synthetic-agent-token" not in repr(config)


def test_optional_send_credential_is_separate_and_redacted(tmp_path: Path) -> None:
    config = CrmBridgeConfig.from_env(_env(tmp_path, MIC_CRM_SEND_API_KEY="synthetic-send-key"))

    assert config.mic_read_api_key == "synthetic-read-key"
    assert config.mic_send_api_key == "synthetic-send-key"
    assert "synthetic-send-key" not in repr(config)


@pytest.mark.parametrize("url", ["http://crm.example.test", "https://crm.example.test"])
def test_remote_crm_requires_explicit_https_opt_in(tmp_path: Path, url: str) -> None:
    with pytest.raises(CrmBridgeConfigError, match="loopback"):
        CrmBridgeConfig.from_env(_env(tmp_path, MIC_CRM_URL=url))


def test_remote_https_is_allowed_only_when_opted_in(tmp_path: Path) -> None:
    config = CrmBridgeConfig.from_env(
        _env(tmp_path, MIC_CRM_URL="https://crm.example.test", MIC_CRM_ALLOW_REMOTE_HTTPS="true")
    )
    assert config.crm_base_url == "https://crm.example.test"


def test_remote_http_is_never_allowed(tmp_path: Path) -> None:
    with pytest.raises(CrmBridgeConfigError, match="loopback"):
        CrmBridgeConfig.from_env(
            _env(tmp_path, MIC_CRM_URL="http://crm.example.test", MIC_CRM_ALLOW_REMOTE_HTTPS="true")
        )


def test_missing_mic_read_credential_fails_closed(tmp_path: Path) -> None:
    env = _env(tmp_path)
    del env["MIC_CRM_READ_API_KEY"]
    with pytest.raises(CrmBridgeConfigError, match="MIC read API key"):
        CrmBridgeConfig.from_env(env)


def test_missing_account_handle_fails_closed(tmp_path: Path) -> None:
    env = _env(tmp_path)
    del env["MIC_ACCOUNT_HANDLE"]
    with pytest.raises(CrmBridgeConfigError, match="account handle"):
        CrmBridgeConfig.from_env(env)


def test_account_handle_is_configured_separately_from_agent_identity(tmp_path: Path) -> None:
    config = CrmBridgeConfig.from_env(
        _env(tmp_path, MIC_ACCOUNT_HANDLE="seller-account-7", MIC_CRM_AGENT_KEY="agent-key")
    )
    assert config.account_handle == "seller-account-7"
    assert config.crm_agent_key == "agent-key"


def test_account_handle_cannot_be_empty(tmp_path: Path) -> None:
    with pytest.raises(CrmBridgeConfigError, match="account handle"):
        CrmBridgeConfig.from_env(_env(tmp_path, MIC_ACCOUNT_HANDLE="  "))
