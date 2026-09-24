from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from enum import StrEnum
from pathlib import Path
from typing import Any, Protocol

from playwright.async_api import Error as PlaywrightError
from playwright.async_api import async_playwright

from mic_gateway.config import Settings


class BrowserSessionState(StrEnum):
    STARTING = "starting"
    AUTHENTICATED = "authenticated"
    OPERATOR_ACTION_REQUIRED = "operator_action_required"
    SITE_CONTRACT_ERROR = "site_contract_error"
    STOPPED = "stopped"


class BrowserRuntimeCrashed(RuntimeError):
    pass


class BrowserLauncher(Protocol):
    async def launch(
        self, user_data_dir: Path, *, headless: bool
    ) -> tuple[Any, Any]: ...


class PlaywrightPersistentLauncher:
    async def launch(self, user_data_dir: Path, *, headless: bool) -> tuple[Any, Any]:
        playwright = await async_playwright().start()
        try:
            context = await playwright.chromium.launch_persistent_context(
                user_data_dir=user_data_dir,
                headless=headless,
            )
        except Exception:
            await playwright.stop()
            raise
        return playwright, context


class BrowserRuntime:
    def __init__(
        self,
        settings: Settings,
        *,
        launcher: BrowserLauncher | None = None,
    ) -> None:
        self.settings = settings
        self.launcher = launcher or PlaywrightPersistentLauncher()
        self.session_state = BrowserSessionState.STOPPED
        self._driver: Any | None = None
        self._context: Any | None = None
        self._page: Any | None = None
        self._operation_lock = asyncio.Lock()
        self._crashed = False

    async def start(self) -> None:
        if self._context is not None and not self._crashed:
            return
        self.session_state = BrowserSessionState.STARTING
        self._crashed = False
        self.settings.browser_profile_dir.mkdir(parents=True, exist_ok=True)
        try:
            self._driver, self._context = await self.launcher.launch(
                self.settings.browser_profile_dir,
                headless=self.settings.chromium_headless,
            )
            pages = list(self._context.pages)
            self._page = pages[0] if pages else await self._context.new_page()
        except Exception:
            self._driver = None
            self._context = None
            self._page = None
            self._crashed = True
            self.session_state = BrowserSessionState.STOPPED
            raise
        self.session_state = BrowserSessionState.OPERATOR_ACTION_REQUIRED

    async def stop(self) -> None:
        context, driver = self._context, self._driver
        self._context = None
        self._driver = None
        self._page = None
        try:
            if context is not None:
                await context.close()
        finally:
            if driver is not None:
                await driver.stop()
            self.session_state = BrowserSessionState.STOPPED

    async def run_serialized[T](
        self,
        operation: Callable[[Any], Awaitable[T]],
    ) -> T:
        if self._crashed or self._page is None:
            raise BrowserRuntimeCrashed("browser runtime is not available")
        async with self._operation_lock:
            if self._crashed or self._page is None:
                raise BrowserRuntimeCrashed("browser runtime is not available")
            try:
                return await operation(self._page)
            except BrowserRuntimeCrashed:
                self._crashed = True
                self.session_state = BrowserSessionState.STOPPED
                raise
            except PlaywrightError as exc:
                self._crashed = True
                self.session_state = BrowserSessionState.STOPPED
                raise BrowserRuntimeCrashed("browser operation failed") from exc

    def mark_authenticated(self) -> None:
        self.session_state = BrowserSessionState.AUTHENTICATED

    def mark_operator_action_required(self) -> None:
        self.session_state = BrowserSessionState.OPERATOR_ACTION_REQUIRED

    def mark_site_contract_error(self) -> None:
        self.session_state = BrowserSessionState.SITE_CONTRACT_ERROR
