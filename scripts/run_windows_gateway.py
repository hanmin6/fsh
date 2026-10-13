"""Run channel collectors and scoped scheduled reception using private configuration."""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit


def configure(config_path: Path) -> dict:
    config = json.loads(config_path.read_text(encoding="utf-8-sig"))
    source = Path(config["sourceRoot"])
    data = Path(config["dataRoot"])
    sys.path[:0] = [str(source / "alibaba-client"), str(source / "mic-client" / "src"), str(Path(__file__).parent)]
    # Legacy/cold outreach stays paused. Only CRM-authorized scheduled intake is consumed.
    os.environ.update({
        "FUSANHE_OUTBOUND_PAUSED": "true",
        "FUSANHE_ALIBABA_DATA_DIR": str(data / "alibaba"),
        "CRM_API_URL": config["crmUrl"] + "/api/v1",
        "FUSANHE_AGENT_KEY": config["alibaba"]["agentKey"],
        "FUSANHE_AGENT_TOKEN": config["alibaba"]["agentToken"],
        "ALIBABA_ACCOUNT_HANDLE": config["alibaba"]["accountHandle"],
        "ALIBABA_SYNC_INTERVAL_SECONDS": "60",
        "MIC_APP_DATA_DIR": str(data / "mic"),
        "MIC_HOST": "127.0.0.1",
        "MIC_PORT": "8787",
        "MIC_CHROMIUM_HEADLESS": "false",
        "MIC_GATEWAY_URL": "http://127.0.0.1:8787",
        "MIC_CRM_URL": config["crmUrl"],
        "MIC_CRM_ALLOW_REMOTE_HTTPS": "true",
        # A full browser sweep reads 12 histories and takes several minutes.
        "MIC_CONVERSATION_STALE_SECONDS": "1800",
        "MIC_CRM_AGENT_KEY": config["mic"]["agentKey"],
        "MIC_CRM_AGENT_TOKEN": config["mic"]["agentToken"],
        "MIC_ACCOUNT_HANDLE": config["mic"]["accountHandle"],
        "FUSANHE_RECOVERY_ENABLED": "true" if config.get("recoveryEnabled") else "false",
        "FUSANHE_RECOVERY_DIR": str(data / "recovery"),
    })
    if config["mic"].get("readApiKey"):
        os.environ["MIC_CRM_READ_API_KEY"] = config["mic"]["readApiKey"]
    os.chdir(source)
    return config


async def setup(config: dict, path: Path) -> None:
    from mic_gateway.api.auth import create_api_key
    from mic_gateway.config import Settings
    from mic_gateway.db.base import Base, create_engine_and_sessionmaker
    from mic_gateway.domain import Role

    settings = Settings()
    settings.app_data_dir.mkdir(parents=True, exist_ok=True)
    engine, sessions = create_engine_and_sessionmaker(settings)
    try:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        if not config["mic"].get("readApiKey"):
            async with sessions() as session:
                config["mic"]["readApiKey"] = await create_api_key(
                    session, "windows-crm-read", Role.CRM_READ
                )
            path.write_text(json.dumps(config, indent=2), encoding="utf-8")
        print("MIC database and read credential ready; outbound worker disabled.", flush=True)
    finally:
        await engine.dispose()


async def alibaba() -> None:
    from alibaba_messenger.alibaba_bot import AlibabaMessengerBot
    from alibaba_messenger.config import settings
    from alibaba_messenger.crm_gateway import CrmGateway
    from alibaba_messenger.sync_service import AlibabaSyncService
    from alibaba_messenger.sync_state import SyncStateStore
    from alibaba_messenger.outbound_worker import OutboundWorker

    crm = CrmGateway(settings.CRM_API_URL, settings.AGENT_KEY, settings.AGENT_TOKEN)
    while True:
        bot = AlibabaMessengerBot()
        if os.environ.get("FUSANHE_RECOVERY_ENABLED") == "true":
            from gateway_recovery_login import handle_recovery
            async def login_recovery(page):
                return await handle_recovery(page, "Alibaba")
            bot.recovery_login_handler = login_recovery
        state = SyncStateStore(settings.SYNC_DB_PATH)
        try:
            await asyncio.to_thread(crm.heartbeat, "offline", "login_required")
            # Startup may wait on a login page. Do not retain the previous
            # process's "ready" file while recovery decides how to log in.
            status_path = Path(settings.BASE_DIR) / "browser-status.json"
            status_path.parent.mkdir(parents=True, exist_ok=True)
            status_path.write_text(json.dumps({"state": "login_required", "page": None}), encoding="utf-8")
            await bot.start(headless=False)
            service = AlibabaSyncService(bot, crm, state, settings)
            outbound = OutboundWorker(bot, crm, settings, scheduled_only=True)
            while True:
                if os.environ.get("FUSANHE_RECOVERY_ENABLED") == "true":
                    from gateway_recovery_login import handle_recovery
                    recovery = await handle_recovery(bot.page, "Alibaba")
                    if recovery == "retry_sync_requested":
                        await bot.page.goto(settings.ALIBABA_MSG_URL, wait_until="domcontentloaded", timeout=30000)
                readiness = await alibaba_readiness(bot.page)
                (Path(settings.BASE_DIR) / "browser-status.json").write_text(
                    json.dumps({"state": readiness,
                                "page": urlsplit(bot.page.url)._replace(query="", fragment="").geturl()
                                if bot.page is not None else None}), encoding="utf-8",
                )
                if readiness == "browser_closed":
                    raise RuntimeError("browser_closed")
                if readiness != "ready":
                    bot.is_logged_in = False
                    await asyncio.to_thread(crm.heartbeat, "offline", readiness)
                    await asyncio.sleep(15)
                    continue
                bot.is_logged_in = True
                try:
                    summary = await service.run_incremental_once()
                    readiness = await alibaba_readiness(bot.page)
                    healthy = summary.failed == 0 and summary.source_checked and readiness == "ready"
                    await asyncio.to_thread(
                        crm.heartbeat, "online" if healthy else "offline",
                        None if healthy else (readiness if readiness != "ready" else "source_sync_unconfirmed"),
                        capture_success={"channelType": "Alibaba", "accountHandle": settings.ACCOUNT_HANDLE} if healthy else None,
                    )
                    if healthy:
                        # Serialize inbound and scheduled replies on the same browser.
                        await outbound.poll_and_execute_once()
                    print(json.dumps({"channel": "Alibaba", "updated": summary.completed,
                                      "failed": summary.failed, "unchanged": summary.skipped,
                                      "sourceChecked": summary.source_checked}), flush=True)
                except Exception as error:
                    print("Alibaba sync failed: " + type(error).__name__, flush=True)
                    await asyncio.to_thread(crm.heartbeat, "offline", "sync_failed")
                await asyncio.sleep(60)
        except Exception as error:
            print("Alibaba restarting: " + type(error).__name__, flush=True)
            try:
                await asyncio.to_thread(crm.heartbeat, "offline", "browser_unavailable")
            except Exception:
                pass
        finally:
            state.close()
            await bot.close()
        await asyncio.sleep(30)


async def alibaba_readiness(page) -> str:
    if page is None or page.is_closed():
        return "browser_closed"
    try:
        if urlsplit(page.url).hostname != "message.alibaba.com":
            return "login_required"
        if await page.locator("input[type=password]:visible").count():
            return "login_required"
        if await page.locator("iframe[src*=captcha]:visible, iframe[src*=verify]:visible").count():
            return "verification_required"
        markers = await page.evaluate("""() => {
            const text = document.body?.innerText || '';
            return !!document.querySelector('.session-item, .contact-item, .im-session-list, [data-testid=conversation-item]')
                || text.includes('商机沟通') || text.includes('询价单号');
        }""")
        return "ready" if markers else "message_page_unconfirmed"
    except Exception:
        return "browser_unavailable"


def mic_status(config: dict) -> dict:
    request = urllib.request.Request(
        "http://127.0.0.1:8787/v1/status",
        headers={"X-API-Key": config["mic"]["readApiKey"]},
    )
    with urllib.request.urlopen(request, timeout=10) as response:
        return json.load(response)


def mic_source_ready(snapshot: dict, now: datetime | None = None) -> bool:
    sync = snapshot.get("sync", {}).get("conversations", {})
    if not isinstance(sync.get("last_success_at"), str):
        return False
    try:
        last_success = datetime.fromisoformat(sync["last_success_at"].replace("Z", "+00:00"))
        age = ((now or datetime.now(timezone.utc)) - last_success).total_seconds()
    except (KeyError, TypeError, ValueError):
        return False
    message_failures = any(v.get("failure_count") for k, v in snapshot.get("sync", {}).items() if k.startswith("messages:"))
    return 0 <= age <= 1800 and not sync.get("failure_count") and not message_failures


def bridge(config: dict) -> None:
    from mic_gateway.crm_bridge.config import CrmBridgeConfig
    from mic_gateway.crm_bridge.crm_client import CrmClient
    from mic_gateway.crm_bridge.importer import MicCrmImporter
    from mic_gateway.crm_bridge.importer import PendingBatchConflictError
    from mic_gateway.crm_bridge.state import CrmBridgeState

    settings = CrmBridgeConfig.from_env()
    crm = CrmClient(config["crmUrl"] + "/api/v1", settings.crm_agent_key, settings.crm_agent_token)
    importer = MicCrmImporter.from_config(
        config=settings, crm=crm, state=CrmBridgeState(settings.app_data_dir),
    )
    while True:
        try:
            snapshot = mic_status(config)
            session = snapshot.get("session", {}).get("state")
            if session != "healthy":
                crm.heartbeat("offline", "login_required" if session in {
                    "authentication_required", "verification_required",
                } else "browser_unavailable")
                print("MIC awaiting authenticated browser.", flush=True)
            else:
                if not mic_source_ready(snapshot):
                    crm.heartbeat("offline", "source_sync_pending_or_failed")
                    print("MIC awaiting a successful source sweep.", flush=True)
                    time.sleep(60)
                    continue
                result = importer.once()
                codes = result.action_required_codes
                crm.heartbeat("offline" if codes else "online", "incomplete_history" if codes else None,
                              capture_success={"channelType": "MadeInChina", "accountHandle": settings.account_handle} if not codes else None)
                print(json.dumps({"channel": "MadeInChina", "conversations": result.conversations,
                                  "messages": result.messages, "actionCodes": codes}), flush=True)
        except PendingBatchConflictError:
            print("MIC bridge pending_batch_conflict", flush=True)
            crm.heartbeat("offline", "pending_batch_conflict")
        except Exception as error:
            print("MIC bridge retry: " + type(error).__name__, flush=True)
            try:
                crm.heartbeat("offline", "gateway_or_sync_unavailable")
            except Exception:
                pass
        time.sleep(60)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("setup", "alibaba", "mic", "bridge", "status"))
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--log-file", type=Path)
    args = parser.parse_args()
    if args.log_file:
        args.log_file.parent.mkdir(parents=True, exist_ok=True)
        log = args.log_file.open("a", encoding="utf-8", buffering=1)
        sys.stdout = sys.stderr = log
    if args.mode != "status":
        print("Gateway starting: " + args.mode, flush=True)
    config = configure(args.config)
    if args.mode == "setup":
        asyncio.run(setup(config, args.config))
    elif args.mode == "alibaba":
        asyncio.run(alibaba())
    elif args.mode == "bridge":
        bridge(config)
    elif args.mode == "status":
        print(json.dumps(mic_status(config), default=str))
    else:
        import uvicorn
        uvicorn.run("mic_gateway.main:create_production_app", factory=True,
                    host="127.0.0.1", port=8787, access_log=False)


if __name__ == "__main__":
    main()
