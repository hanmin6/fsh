from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlsplit


class CrmBridgeConfigError(ValueError):
    """Raised when bridge settings are unsafe or incomplete."""


@dataclass(frozen=True, slots=True)
class CrmBridgeConfig:
    app_data_dir: Path
    mic_base_url: str
    mic_read_api_key: str = field(repr=False)
    crm_base_url: str
    crm_agent_key: str
    account_handle: str
    mic_send_api_key: str | None = field(default=None, repr=False)
    crm_agent_token: str | None = field(default=None, repr=False)
    crm_bootstrap_token: str | None = field(default=None, repr=False)
    allow_remote_crm: bool = False

    @classmethod
    def from_env(cls, environ: dict[str, str] | None = None) -> CrmBridgeConfig:
        env = os.environ if environ is None else environ
        app_data = env.get("MIC_APP_DATA_DIR")
        if not app_data:
            raise CrmBridgeConfigError("MIC_APP_DATA_DIR is required")
        allow_remote = env.get("MIC_CRM_ALLOW_REMOTE_HTTPS", "false").strip().lower() in {
            "1",
            "true",
            "yes",
        }
        config = cls(
            app_data_dir=Path(app_data).expanduser().resolve(),
            mic_base_url=env.get("MIC_GATEWAY_URL", "http://127.0.0.1:8787").rstrip("/"),
            mic_read_api_key=env.get("MIC_CRM_READ_API_KEY", ""),
            crm_base_url=env.get("MIC_CRM_URL", "http://127.0.0.1:8080").rstrip("/"),
            crm_agent_key=env.get("MIC_CRM_AGENT_KEY", "mic-agent"),
            account_handle=env.get("MIC_ACCOUNT_HANDLE", ""),
            mic_send_api_key=env.get("MIC_CRM_SEND_API_KEY") or None,
            crm_agent_token=env.get("MIC_CRM_AGENT_TOKEN") or None,
            crm_bootstrap_token=env.get("MIC_CRM_BOOTSTRAP_TOKEN") or None,
            allow_remote_crm=allow_remote,
        )
        config.validate()
        return config

    def validate(self) -> None:
        _validate_local_or_opted_https(
            self.mic_base_url, allow_remote_https=False, label="MIC gateway"
        )
        _validate_local_or_opted_https(
            self.crm_base_url,
            allow_remote_https=self.allow_remote_crm,
            label="CRM",
        )
        if not self.mic_read_api_key:
            raise CrmBridgeConfigError("MIC read API key is required")
        if not self.crm_agent_key:
            raise CrmBridgeConfigError("CRM Agent key is required")
        if not self.account_handle.strip():
            raise CrmBridgeConfigError("MIC account handle is required")


def _validate_local_or_opted_https(url: str, *, allow_remote_https: bool, label: str) -> None:
    parsed = urlsplit(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise CrmBridgeConfigError(f"{label} URL must be an absolute HTTP(S) URL")
    host = parsed.hostname.lower()
    is_loopback = host == "localhost" or host.endswith(".localhost") or host == "::1"
    if not is_loopback:
        try:
            import ipaddress

            is_loopback = ipaddress.ip_address(host).is_loopback
        except ValueError:
            is_loopback = False
    if is_loopback:
        return
    if parsed.scheme == "https" and allow_remote_https:
        return
    raise CrmBridgeConfigError(
        f"{label} must use a loopback URL unless remote HTTPS is explicitly enabled"
    )
