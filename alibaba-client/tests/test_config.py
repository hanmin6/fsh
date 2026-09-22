import os
from pathlib import Path

import pytest

from alibaba_crm_client import AlibabaCRMClient
from alibaba_messenger.config import Settings


def test_crm_sync_defaults_are_safe(tmp_path, monkeypatch):
    for variable in (
        "CRM_API_URL",
        "FUSANHE_AGENT_KEY",
        "FUSANHE_AGENT_TOKEN",
        "ALIBABA_ACCOUNT_HANDLE",
        "ALIBABA_SYNC_INTERVAL_SECONDS",
        "ALIBABA_SYNC_BATCH_SIZE",
        "ALIBABA_SYNC_DB_PATH",
        "BACKFILL_MAX_PAGES",
    ):
        monkeypatch.delenv(variable, raising=False)

    settings = Settings(BASE_DIR=str(tmp_path))

    assert settings.CRM_API_URL == "http://localhost:8080/api/v1"
    assert settings.AGENT_KEY == "guangzhou-alibaba-01"
    assert settings.AGENT_TOKEN == ""
    assert settings.ACCOUNT_HANDLE == "default"
    assert settings.SYNC_INTERVAL_SECONDS == 300
    assert settings.SYNC_BATCH_SIZE == 100
    assert settings.SYNC_DB_PATH.endswith("alibaba_sync.db")
    assert settings.BACKFILL_MAX_PAGES == 1000


def test_crm_sync_environment_overrides_are_applied(tmp_path, monkeypatch):
    monkeypatch.setenv("CRM_API_URL", "https://crm.example.test/api/")
    monkeypatch.setenv("FUSANHE_AGENT_KEY", "test-agent")
    monkeypatch.setenv("FUSANHE_AGENT_TOKEN", "test-token")
    monkeypatch.setenv("ALIBABA_ACCOUNT_HANDLE", "test-account")
    monkeypatch.setenv("ALIBABA_SYNC_INTERVAL_SECONDS", "60")
    monkeypatch.setenv("ALIBABA_SYNC_BATCH_SIZE", "25")
    monkeypatch.setenv("ALIBABA_SYNC_DB_PATH", str(tmp_path / "state.db"))
    monkeypatch.setenv("BACKFILL_MAX_PAGES", "200")

    settings = Settings(BASE_DIR=str(tmp_path))

    assert settings.CRM_API_URL == "https://crm.example.test/api"
    assert settings.AGENT_KEY == "test-agent"
    assert settings.AGENT_TOKEN == "test-token"
    assert settings.ACCOUNT_HANDLE == "test-account"
    assert settings.SYNC_INTERVAL_SECONDS == 60
    assert settings.SYNC_BATCH_SIZE == 25
    assert settings.SYNC_DB_PATH == str(tmp_path / "state.db")
    assert settings.BACKFILL_MAX_PAGES == 200


def test_base_dir_controls_all_derived_paths(tmp_path):
    settings = Settings(BASE_DIR=str(tmp_path))

    for path in (
        settings.PROFILE_DIR,
        settings.LOGS_DIR,
        settings.SCREENSHOTS_DIR,
        settings.SENT_RECORDS_FILE,
        settings.SYNC_DB_PATH,
    ):
        assert Path(path).is_relative_to(tmp_path)


def test_client_reads_credentials_at_initialization(monkeypatch):
    monkeypatch.setenv("ALIBABA_APP_KEY", "test-key")
    monkeypatch.setenv("ALIBABA_APP_SECRET", "test-secret")
    monkeypatch.setattr(AlibabaCRMClient, "_load_token", lambda self: {})

    client = AlibabaCRMClient()

    assert client.app_key == "test-key"
    assert client.app_secret == "test-secret"


@pytest.mark.parametrize(
    ("app_key", "app_secret"),
    (("", "test-secret"), ("test-key", "")),
)
def test_client_rejects_missing_credentials_before_loading_token(
    monkeypatch, app_key, app_secret
):
    monkeypatch.setattr(
        AlibabaCRMClient,
        "_load_token",
        lambda self: (_ for _ in ()).throw(AssertionError("token load should not run")),
    )

    with pytest.raises(ValueError):
        AlibabaCRMClient(app_key=app_key, app_secret=app_secret)


def test_settings_paths_and_defaults():
    settings = Settings()
    assert os.path.isabs(settings.BASE_DIR)
    assert os.path.isabs(settings.PROFILE_DIR)
    assert os.path.isabs(settings.LOGS_DIR)
    assert os.path.isabs(settings.SCREENSHOTS_DIR)
    assert settings.SERVER_PORT == 8000
    assert settings.TYPING_DELAY_MIN_MS == 20
    assert settings.TYPING_DELAY_MAX_MS == 80
