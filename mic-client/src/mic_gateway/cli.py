from __future__ import annotations

import argparse
import asyncio
from collections.abc import Callable, Sequence
from typing import Protocol

from mic_gateway.adapters.base import SessionHealth
from mic_gateway.adapters.made_in_china import MadeInChinaAdapter
from mic_gateway.api.auth import create_api_key, revoke_api_key
from mic_gateway.browser.discovery import discover_resource
from mic_gateway.browser.runtime import BrowserRuntime
from mic_gateway.config import Settings, get_settings
from mic_gateway.db.base import create_engine_and_sessionmaker
from mic_gateway.domain import Role


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="mic-gateway")
    commands = parser.add_subparsers(dest="command", required=True)
    create_key = commands.add_parser("create-api-key")
    create_key.add_argument("--name", required=True)
    create_key.add_argument("--role", required=True, choices=[role.value for role in Role])
    revoke_key = commands.add_parser("revoke-api-key")
    revoke_key.add_argument("--name", required=True)
    commands.add_parser("browser-login")
    discover = commands.add_parser("discover")
    discover.add_argument(
        "--resource", required=True, choices=["orders", "conversations", "messages"]
    )
    return parser


async def _create_key(name: str, role: Role) -> str:
    settings = get_settings()
    settings.app_data_dir.mkdir(parents=True, exist_ok=True)
    engine, sessions = create_engine_and_sessionmaker(settings)
    try:
        async with sessions() as session:
            return await create_api_key(session, name, role)
    finally:
        await engine.dispose()


async def _revoke_key(name: str) -> bool:
    settings = get_settings()
    engine, sessions = create_engine_and_sessionmaker(settings)
    try:
        async with sessions() as session:
            return await revoke_api_key(session, name)
    finally:
        await engine.dispose()


class SessionProbe(Protocol):
    async def check_session(self, runtime: BrowserRuntime) -> SessionHealth: ...


class ManualSessionProbe:
    """Temporary probe replaced by the production positive-marker adapter in Task 13."""

    async def check_session(self, runtime: BrowserRuntime) -> SessionHealth:
        return SessionHealth.available()


class MadeInChinaSessionProbe:
    async def check_session(self, runtime: BrowserRuntime) -> SessionHealth:
        return await MadeInChinaAdapter(runtime).check_session()


async def browser_login(
    settings: Settings,
    *,
    probe: SessionProbe,
    confirm: Callable[[str], str] = input,
) -> int:
    headed_settings = settings.model_copy(update={"chromium_headless": False})
    runtime = BrowserRuntime(headed_settings)
    await runtime.start()
    try:
        await runtime.run_serialized(lambda page: page.goto(settings.seller_url))
        await asyncio.to_thread(
            confirm,
            "Complete login in the dedicated browser, then press Enter to verify: ",
        )
        health = await probe.check_session(runtime)
        if health.healthy:
            runtime.mark_authenticated()
            print("Dedicated Made-in-China browser profile is ready.")
            return 0
        runtime.mark_operator_action_required()
        print(f"Login verification failed: {health.detail_code or health.state.value}")
        return 1
    finally:
        await runtime.stop()


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "create-api-key":
        raw_key = asyncio.run(_create_key(args.name, Role(args.role)))
        print(raw_key)
        return 0
    if args.command == "revoke-api-key":
        revoked = asyncio.run(_revoke_key(args.name))
        print("API key revoked." if revoked else "API key was not active or not found.")
        return 0 if revoked else 1
    if args.command == "browser-login":
        return asyncio.run(
            browser_login(get_settings(), probe=MadeInChinaSessionProbe())
        )
    if args.command == "discover":
        paths = asyncio.run(discover_resource(get_settings(), args.resource))
        for path in paths:
            print(path)
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
