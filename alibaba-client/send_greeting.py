# -*- coding: utf-8 -*-
"""Execute sending the approved inquiry progress greeting to Jing Liu."""
from __future__ import annotations

import argparse
import asyncio
import os
import sys
import time
from pathlib import Path

# Ensure repo root is on sys.path
repo_root = Path(__file__).resolve().parent
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

from dotenv import load_dotenv
env_path = repo_root / ".env"
if env_path.exists():
    load_dotenv(env_path, override=True)

from alibaba_messenger.alibaba_bot import AlibabaMessengerBot, SendResultStatus
from alibaba_messenger.config import settings
from alibaba_messenger.crm_gateway import CrmGateway
from alibaba_messenger.sync_models import SyncMessage
from alibaba_messenger.sync_service import build_sync_payload, stable_request_id

BUYER_NAME = "Jing Liu"
INQUIRY_ID = "20504334932"
APPROVED_MESSAGE = (
    "Hi Jenny, hope you're having a great week!\n"
    "Checking in regarding the 750g - 2kg boxed Baking Soda project for your supermarket channels. "
    "Did you have a chance to review the email sent to jenny@icbltd.com.au? "
    "We are fully ready to provide custom box samples and spec sheets. "
    "Looking forward to your update!"
)


async def send_greeting(headless: bool = False, force: bool = False) -> int:
    print("=" * 70)
    print(f"[Send] 目标买家: {BUYER_NAME} (商机单号: {INQUIRY_ID})")
    print(f"[Send] 发送模式: {'无头模式 (Headless)' if headless else '有头交互模式 (Headful)'}")
    print("[Send] 审核通过的发送内容:")
    print("-" * 50)
    print(APPROVED_MESSAGE)
    print("-" * 50)

    bot = AlibabaMessengerBot()
    try:
        print("[Bot] 启动持久化浏览器会话...")
        await bot.start(headless=headless)
        if not bot.is_logged_in:
            print("[Error] 阿里国际站未处于登录状态，请先在界面完成登录！", file=sys.stderr)
            return 1

        print(f"[Bot] 正在向买家 [{BUYER_NAME}] (商机单号: {INQUIRY_ID}) 发送消息...")
        res = await bot.send_message(
            buyer_name=BUYER_NAME,
            message=APPROVED_MESSAGE,
            inquiry_id=INQUIRY_ID,
            force_send=force,
        )

        success = res.get("success", False)
        status = res.get("status", "UNKNOWN")
        msg = res.get("message", "")
        data = res.get("data", {})

        if success:
            print("\n" + "=" * 70)
            print(f"[Success] 消息发送成功！状态: {status}")
            print(f"[Info] 耗时: {data.get('elapsed_seconds')} 秒")
            print(f"[Info] 截图留证: {data.get('screenshot')}")
            print("=" * 70 + "\n")

            # 同步回写 CRM
            from alibaba_messenger.config import Settings
            current_settings = Settings()
            if current_settings.AGENT_TOKEN:
                try:
                    print("[CRM] 正在将出向消息回写至本地 CRM...")
                    gateway = CrmGateway(current_settings.CRM_API_URL, current_settings.AGENT_KEY, current_settings.AGENT_TOKEN)
                    sent_msg = SyncMessage.from_source(
                        inquiry_id=INQUIRY_ID,
                        sender="seller",
                        content=APPROVED_MESSAGE,
                        raw_time=data.get("sent_at") or time.strftime("%Y-%m-%d %H:%M:%S"),
                        sequence=999,
                        platform_id=f"ALI-OUT-{int(time.time())}",
                    )
                    job_id = f"single-send-{int(time.time())}"
                    request_id = stable_request_id(job_id, INQUIRY_ID, 1)
                    conv_payload = {
                        "inquiry_id": INQUIRY_ID,
                        "buyer_name": BUYER_NAME,
                        "country": "",
                        "last_message": APPROVED_MESSAGE,
                        "last_time": time.strftime("%Y-%m-%d %H:%M:%S"),
                    }
                    payload = build_sync_payload(
                        job_id=job_id,
                        request_id=request_id,
                        account_handle=current_settings.ACCOUNT_HANDLE,
                        conversation=conv_payload,
                        messages=[sent_msg],
                        batch_no=1,
                        final_batch=True,
                    )
                    gateway.sync_batch(payload, request_id)
                    print("[CRM] 成功回写至 CRM 系统！")
                except Exception as crm_err:
                    print(f"[CRM Warning] 回写 CRM 异常 (不影响阿里实际发送): {crm_err}")

            return 0
        else:
            print(f"\n[Failed] 消息发送未完成: {status} - {msg}", file=sys.stderr)
            if data.get("screenshot_path"):
                print(f"[Debug] 异常截图: {data.get('screenshot_path')}", file=sys.stderr)
            return 2
    finally:
        await bot.close()


def main():
    p = argparse.ArgumentParser(description="Send approved greeting to Jing Liu")
    p.add_argument("--headless", action="store_true", help="Run browser in headless mode")
    p.add_argument("--force", action="store_true", help="Force send ignoring dedup")
    args = p.parse_args()
    return asyncio.run(send_greeting(headless=args.headless, force=args.force))


if __name__ == "__main__":
    raise SystemExit(main())
