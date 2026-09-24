from __future__ import annotations

from pathlib import Path

import pytest

from mic_gateway.browser.runtime import (
    BrowserRuntime,
    BrowserRuntimeCrashed,
    BrowserSessionState,
)
from mic_gateway.cli import build_parser
from mic_gateway.config import Settings


class FakePage:
    def __init__(self) -> None:
        self.urls: list[str] = []

    async def goto(self, url: str) -> None:
        self.urls.append(url)


class FakeContext:
    def __init__(self, page: FakePage | None = None) -> None:
        self.pages = [page] if page is not None else []
        self.created_page = FakePage()
        self.closed = False

    async def new_page(self) -> FakePage:
        self.pages.append(self.created_page)
        return self.created_page

    async def close(self) -> None:
        self.closed = True


class FakeDriver:
    def __init__(self) -> None:
        self.stopped = False

    async def stop(self) -> None:
        self.stopped = True


class FakeLauncher:
    def __init__(self, context: FakeContext | None = None) -> None:
        self.context = context or FakeContext()
        self.driver = FakeDriver()
        self.calls: list[tuple[Path, bool]] = []

    async def launch(
        self, user_data_dir: Path, *, headless: bool
    ) -> tuple[FakeDriver, FakeContext]:
        self.calls.append((user_data_dir, headless))
        return self.driver, self.context


@pytest.mark.asyncio
async def test_runtime_uses_dedicated_profile_and_closes_cleanly(tmp_path: Path) -> None:
    settings = Settings(app_data_dir=tmp_path, chromium_headless=True)
    retained_page = FakePage()
    launcher = FakeLauncher(FakeContext(retained_page))
    runtime = BrowserRuntime(settings, launcher=launcher)

    await runtime.start()
    page = await runtime.run_serialized(lambda current: current.goto("https://example.test"))
    await runtime.stop()

    assert page is None
    assert launcher.calls == [(tmp_path / "browser-profile", True)]
    assert retained_page.urls == ["https://example.test"]
    assert launcher.context.closed is True
    assert launcher.driver.stopped is True
    assert runtime.session_state is BrowserSessionState.STOPPED


@pytest.mark.asyncio
async def test_runtime_creates_one_page_when_profile_has_none(tmp_path: Path) -> None:
    launcher = FakeLauncher()
    runtime = BrowserRuntime(Settings(app_data_dir=tmp_path), launcher=launcher)

    await runtime.start()
    await runtime.run_serialized(lambda page: page.goto("https://example.test"))

    assert launcher.context.created_page.urls == ["https://example.test"]


@pytest.mark.asyncio
async def test_runtime_crash_fails_closed_and_rejects_later_operations(tmp_path: Path) -> None:
    runtime = BrowserRuntime(Settings(app_data_dir=tmp_path), launcher=FakeLauncher())
    await runtime.start()

    async def crash(_: FakePage) -> None:
        raise BrowserRuntimeCrashed("browser closed")

    with pytest.raises(BrowserRuntimeCrashed):
        await runtime.run_serialized(crash)
    with pytest.raises(BrowserRuntimeCrashed):
        await runtime.run_serialized(lambda page: page.goto("https://example.test"))

    assert runtime.session_state is BrowserSessionState.STOPPED


def test_session_state_transitions_are_explicit(tmp_path: Path) -> None:
    runtime = BrowserRuntime(Settings(app_data_dir=tmp_path), launcher=FakeLauncher())

    assert runtime.session_state is BrowserSessionState.STOPPED
    runtime.mark_operator_action_required()
    assert runtime.session_state is BrowserSessionState.OPERATOR_ACTION_REQUIRED
    runtime.mark_authenticated()
    assert runtime.session_state is BrowserSessionState.AUTHENTICATED
    runtime.mark_site_contract_error()
    assert runtime.session_state is BrowserSessionState.SITE_CONTRACT_ERROR


def test_cli_exposes_browser_login_command() -> None:
    args = build_parser().parse_args(["browser-login"])

    assert args.command == "browser-login"


def test_cli_exposes_api_key_revocation_command() -> None:
    args = build_parser().parse_args(["revoke-api-key", "--name", "crm-old"])

    assert args.command == "revoke-api-key"
    assert args.name == "crm-old"
