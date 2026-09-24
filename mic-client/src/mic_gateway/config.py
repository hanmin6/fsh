from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Self

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Validated runtime configuration."""

    model_config = SettingsConfigDict(
        env_prefix="MIC_",
        env_file=".env",
        extra="forbid",
    )

    app_data_dir: Path
    host: str = "0.0.0.0"
    port: int = 8787
    conversation_sync_seconds: int = 30
    order_sync_seconds: int = 300
    conversation_stale_seconds: int = 120
    order_stale_seconds: int = 900
    seller_url: str = "https://membercenter.made-in-china.com/"
    send_interval_seconds: int = 10
    database_url: str | None = None
    chromium_headless: bool = False
    max_request_bytes: int = 65_536

    @model_validator(mode="after")
    def validate_app_data_location(self) -> Self:
        source_root = Path.cwd().resolve()
        app_data_dir = self.app_data_dir.expanduser().resolve()
        if app_data_dir.is_relative_to(source_root):
            raise ValueError("app_data_dir must be outside the source tree")
        self.app_data_dir = app_data_dir
        return self

    @property
    def browser_profile_dir(self) -> Path:
        return self.app_data_dir / "browser-profile"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    # BaseSettings supplies required values from the environment at runtime.
    return Settings()  # type: ignore[call-arg]
