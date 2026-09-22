"""Operator CLI for one-time registration and resumable Alibaba backfill."""
from __future__ import annotations

import argparse
import asyncio
import ipaddress
import os
import sys
from pathlib import Path
from urllib.parse import urlparse

if __package__ is None or not __package__:
    repo_root = Path(__file__).resolve().parent.parent
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

from alibaba_messenger.alibaba_bot import AlibabaMessengerBot
from alibaba_messenger.config import Settings
from alibaba_messenger.crm_gateway import CrmGateway
from alibaba_messenger.sync_service import AlibabaSyncService
from alibaba_messenger.sync_state import SyncStateStore, read_status


def _is_loopback(url: str) -> bool:
    host = urlparse(url).hostname
    if host == "localhost": return True
    try: return bool(host and ipaddress.ip_address(host).is_loopback)
    except ValueError: return False


def _require_safe_url(url: str, allow_remote: bool) -> None:
    parsed = urlparse(url)
    if _is_loopback(url): return
    if not allow_remote or parsed.scheme != "https":
        raise ValueError("CRM URL must be loopback; remote CRM requires --allow-remote and https")


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description="Alibaba inquiry import & incremental sync daemon (no outbound sending)")
    result.add_argument("command", choices=("register", "backfill", "once", "daemon", "status"))
    result.add_argument("--headless", action="store_true")
    result.add_argument("--allow-remote", action="store_true")
    result.add_argument("--interval", type=int, default=None, help="polling interval in seconds for daemon (default: 300)")
    result.add_argument("--bootstrap", help="bootstrap credential for register only")
    return result


async def _backfill(settings: Settings, headless: bool) -> int:
    if not settings.AGENT_TOKEN:
        print("FUSANHE_AGENT_TOKEN is required for backfill.", file=sys.stderr)
        return 2
    print(f"[Sync] 目标 CRM API: {settings.CRM_API_URL}, Agent Key: {settings.AGENT_KEY}")
    bot = AlibabaMessengerBot()
    state = SyncStateStore(settings.SYNC_DB_PATH)
    try:
        await bot.start(headless=headless)
        if not bot.is_logged_in:
            print("Alibaba login is required before backfill.", file=sys.stderr)
            return 2
        summary = await AlibabaSyncService(
            bot, CrmGateway(settings.CRM_API_URL, settings.AGENT_KEY, settings.AGENT_TOKEN), state, settings
        ).run_backfill()
        print(f"backfill job={summary.job_id} completed={summary.completed} failed={summary.failed} skipped={summary.skipped}")
        return 0
    finally:
        state.close()
        await bot.close()


async def _once(settings: Settings, headless: bool) -> int:
    if not settings.AGENT_TOKEN:
        print("FUSANHE_AGENT_TOKEN is required for sync.", file=sys.stderr)
        return 2
    print(f"[Sync] 目标 CRM API: {settings.CRM_API_URL}, Agent Key: {settings.AGENT_KEY}")
    bot = AlibabaMessengerBot()
    state = SyncStateStore(settings.SYNC_DB_PATH)
    try:
        await bot.start(headless=headless)
        if not bot.is_logged_in:
            print("Alibaba login is required before sync.", file=sys.stderr)
            return 2
        summary = await AlibabaSyncService(
            bot, CrmGateway(settings.CRM_API_URL, settings.AGENT_KEY, settings.AGENT_TOKEN), state, settings
        ).run_incremental_once()
        print(f"incremental sync job={summary.job_id} updated={summary.completed} skipped={summary.skipped} failed={summary.failed}")
        return 0
    finally:
        state.close()
        await bot.close()


async def _daemon(settings: Settings, headless: bool, interval: int) -> int:
    if not settings.AGENT_TOKEN:
        print("FUSANHE_AGENT_TOKEN is required for daemon.", file=sys.stderr)
        return 2
    print(f"[Daemon] 目标 CRM API: {settings.CRM_API_URL}, Agent Key: {settings.AGENT_KEY}")
    bot = AlibabaMessengerBot()
    state = SyncStateStore(settings.SYNC_DB_PATH)
    stop_event = asyncio.Event()
    try:
        await bot.start(headless=headless)
        if not bot.is_logged_in:
            print("Alibaba login is required before running daemon.", file=sys.stderr)
            return 2
        service = AlibabaSyncService(
            bot, CrmGateway(settings.CRM_API_URL, settings.AGENT_KEY, settings.AGENT_TOKEN), state, settings
        )
        await service.run_daemon(interval=interval, stop_event=stop_event)
        return 0
    except (asyncio.CancelledError, KeyboardInterrupt):
        print("\n[Daemon] 收到终止信号，正在关闭...")
        return 0
    finally:
        state.close()
        await bot.close()


def main(argv=None) -> int:
    try:
        from dotenv import load_dotenv
        env_file = Path(__file__).resolve().parent.parent / ".env"
        if env_file.exists():
            load_dotenv(env_file, override=True)
        else:
            load_dotenv(override=True)
    except ImportError:
        pass
    args = parser().parse_args(argv)
    settings = Settings()
    try:
        _require_safe_url(settings.CRM_API_URL, args.allow_remote)
        if args.command == "status":
            print(read_status(settings.SYNC_DB_PATH))
            return 0
        if args.command == "register":
            bootstrap = args.bootstrap or os.getenv("FUSANHE_BOOTSTRAP_TOKEN", "")
            if not bootstrap:
                print("A bootstrap credential is required for register.", file=sys.stderr)
                return 2
            token = CrmGateway(settings.CRM_API_URL, settings.AGENT_KEY, "").register(bootstrap, rotate=True)
            print("Save this one-time token immediately as FUSANHE_AGENT_TOKEN (it is not written to disk):")
            print(token)
            return 0
        if args.command == "once":
            return asyncio.run(_once(settings, args.headless))
        if args.command == "daemon":
            interval = args.interval or settings.SYNC_INTERVAL_SECONDS
            return asyncio.run(_daemon(settings, args.headless, interval))
        return asyncio.run(_backfill(settings, args.headless))
    except (ValueError, RuntimeError) as exc:
        print(str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
