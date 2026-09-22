# -*- coding: utf-8 -*-
"""Operator CLI for Alibaba Messenger Outbound Worker and Heartbeat Daemon."""
from __future__ import annotations

import argparse
import asyncio
import ipaddress
import logging
import os
import signal
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
from alibaba_messenger.outbound_worker import OutboundWorker

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("run_worker")


def _is_loopback(url: str) -> bool:
    host = urlparse(url).hostname
    if host == "localhost":
        return True
    try:
        return bool(host and ipaddress.ip_address(host).is_loopback)
    except ValueError:
        return False


def _require_safe_url(url: str, allow_remote: bool) -> None:
    parsed = urlparse(url)
    if _is_loopback(url):
        return
    if not allow_remote or parsed.scheme != "https":
        raise ValueError("CRM URL must be loopback; remote CRM requires --allow-remote and https")


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Alibaba Outbound Worker & Heartbeat Daemon")
    p.add_argument("--headless", action="store_true", help="Run browser in headless mode")
    p.add_argument("--allow-remote", action="store_true", help="Allow remote CRM URL via HTTPS")
    p.add_argument("--interval", type=float, default=15.0, help="Claim poll interval in seconds (default: 15)")
    p.add_argument("--heartbeat-interval", type=float, default=60.0, help="Heartbeat interval in seconds (default: 60)")
    p.add_argument("--dry-run", action="store_true", help="Simulate outbound sending without invoking real browser keystrokes")
    p.add_argument("--once", action="store_true", help="Run a single heartbeat and single claim poll tick, then exit")
    return p


async def _run_worker(settings: Settings, args: argparse.Namespace) -> int:
    if not settings.AGENT_TOKEN:
        print("[Worker] FUSANHE_AGENT_TOKEN is required to communicate with CRM.", file=sys.stderr)
        return 2

    print(f"[Worker] 启动 Outbound Worker, 目标 CRM API: {settings.CRM_API_URL}, Agent Key: {settings.AGENT_KEY}")
    gateway = CrmGateway(settings.CRM_API_URL, settings.AGENT_KEY, settings.AGENT_TOKEN)

    bot = None
    if not args.dry_run:
        bot = AlibabaMessengerBot()
        await bot.start(headless=args.headless)
        if not bot.is_logged_in:
            print("[Worker] 注意：阿里未处于登录态，将上报 offline 心跳，请扫码登录。", file=sys.stderr)
    else:
        print("[Worker] 模式：--dry-run（模拟运行，不启动真实浏览器）")

        class DryRunBot:
            is_logged_in = True

            async def send_message(self, *a, **kw):
                return {"success": True, "message": "dry-run success"}

            async def close(self):
                pass

        bot = DryRunBot()

    worker = OutboundWorker(
        bot=bot,
        gateway=gateway,
        settings=settings,
        dry_run=args.dry_run,
    )

    try:
        if args.once:
            print("[Worker] 执行单次心跳与轮询 (--once)...")
            await worker.send_heartbeat()
            await worker.poll_and_execute_once()
            print("[Worker] 单次执行完毕，退出。")
            return 0

        stop_event = asyncio.Event()

        # Handle signals for graceful shutdown where available
        try:
            loop = asyncio.get_running_loop()
            for sig in (signal.SIGINT, signal.SIGTERM):
                loop.add_signal_handler(sig, stop_event.set)
        except (NotImplementedError, AttributeError):
            pass

        await worker.run_loop(
            stop_event=stop_event,
            poll_interval=args.interval,
            heartbeat_interval=args.heartbeat_interval,
        )
        return 0
    finally:
        if bot and hasattr(bot, "close"):
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
        return asyncio.run(_run_worker(settings, args))
    except (ValueError, RuntimeError, KeyboardInterrupt) as exc:
        print(f"[Worker Error] {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
