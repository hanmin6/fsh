import asyncio
import hashlib
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

repo_src = Path(r"G:\FSH\made-in-china\made-in-china\src")
if str(repo_src) not in sys.path:
    sys.path.insert(0, str(repo_src))

from mic_gateway.adapters.made_in_china import MadeInChinaAdapter
from mic_gateway.browser.runtime import BrowserRuntime
from mic_gateway.config import get_settings
from mic_gateway.db.base import create_engine_and_sessionmaker
from mic_gateway.db.models import ApiKey, OutboxJob
from mic_gateway.db.repositories import (
    CheckpointRepository,
    ConversationRepository,
    MessageRepository,
    OrderRepository,
    OutboxRepository,
)
from mic_gateway.domain import JobState, MessageIntent, OutboxCreateRequest
from mic_gateway.messaging.outbox import OutboxWorker
from mic_gateway.policies.messages import evaluate_message
from sqlalchemy import select

TARGET_CONV_SOURCE_ID = "rwKpdOGJfYoM"
TARGET_BUYER_NAME = "Mireille Sacrifice"
TARGET_BUYER_REF = "EEnxEJQbMJmm"

CONTENT = """Bonjour M. Mireille Sacrifice,

Nous faisons suite à votre demande concernant notre poudre d'attendrisseur de viande.

Avez-vous des nouvelles ou des besoins particuliers concernant l'avancement de votre projet ? Nous restons à votre entière disposition.

Cordialement,
Guangzhou Fusanhe Food Co., Ltd"""

async def main():
    settings = get_settings()
    engine, sessions = create_engine_and_sessionmaker(settings)
    
    # 1. Verify policy
    decision = evaluate_message(MessageIntent.NON_COMMERCIAL_FOLLOWUP, CONTENT)
    if not decision.allowed:
        print(f"FAILED: Message rejected by policy: {decision.code}")
        return

    # 2. Get API key ID for audit trail
    async with sessions() as session:
        key_row = (await session.execute(select(ApiKey).where(ApiKey.role == "agent_send"))).scalars().first()
        agent_key_id = key_row.id if key_row else None
        
        # Verify conversation in DB
        conv_repo = ConversationRepository(sessions)
        conv = await conv_repo.get_by_source_id(TARGET_CONV_SOURCE_ID)
        if not conv:
            print(f"FAILED: Conversation {TARGET_CONV_SOURCE_ID} not in local DB")
            return
        conv_id = conv.id

    # 3. Ensure Outbox Job exists
    outbox_repo = OutboxRepository(sessions)
    async with sessions() as session:
        existing_job = (
            await session.execute(
                select(OutboxJob).where(
                    OutboxJob.conversation_id == conv_id,
                    OutboxJob.state.in_(["queued", "sending"]),
                )
            )
        ).scalars().first()

    if existing_job:
        job = existing_job
        print(f"Using existing Outbox Job: {job.id}, state={job.state}")
    else:
        payload = {
            "conversation_id": str(conv_id),
            "intent": MessageIntent.NON_COMMERCIAL_FOLLOWUP.value,
            "content": CONTENT,
            "caller_reference": "manual-test-agent",
        }
        canonical = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode()
        digest = hashlib.sha256(canonical).hexdigest()

        req = OutboxCreateRequest(
            idempotency_key=f"live-send-{TARGET_CONV_SOURCE_ID}",
            payload_digest=digest,
            conversation_id=conv_id,
            intent=MessageIntent.NON_COMMERCIAL_FOLLOWUP,
            content=CONTENT,
            caller_reference="manual-test-agent",
            caller_key_id=agent_key_id,
            request_id=f"req-live-send-{int(datetime.now(UTC).timestamp())}",
            initial_state=JobState.QUEUED,
        )
        result = await outbox_repo.create_idempotent(req)
        job = result.job
        print(f"Created Outbox Job: {job.id}, state={job.state}")

    print("\n" + "=" * 60)
    print(f"目标买家: {TARGET_BUYER_NAME} ({TARGET_BUYER_REF})")
    print(f"会话 ID: {TARGET_CONV_SOURCE_ID}")
    print("发送内容 (审核通过版本 2):")
    print("-" * 60)
    print(CONTENT)
    print("=" * 60 + "\n")

    # 4. Launch BrowserRuntime and execute send through adapter and outbox worker
    runtime = BrowserRuntime(settings.model_copy(update={"chromium_headless": False}))
    await runtime.start()
    try:
        adapter = MadeInChinaAdapter(runtime)
        print("Checking session health before send...")
        health = await adapter.check_session()
        print(f"Session health: {health.healthy}, state={health.state.value}")
        if not health.healthy:
            print("\n>>> 检测到需要登录。请在弹出的 Chromium 浏览器中登录账号并进入询盘后台。")
            await asyncio.to_thread(input, ">>> 登录完成后，请回到此处按回车键继续发送: ")
            health = await adapter.check_session()
            if not health.healthy:
                print(f"FAILED: 登录校验未通过 ({health.detail_code or health.state.value})")
                return
            print(">>> 登录态确认成功！开始执行发信流程...")

        outbox_worker = OutboxWorker(
            jobs=outbox_repo,
            adapter=adapter,
            runtime=runtime,
            send_interval_seconds=1.0,
        )
        print("OutboxWorker executing run_once()...")
        updated_job = await outbox_worker.run_once()
        if updated_job:
            print(f"\nJob ID: {updated_job.id}")
            print(f"Final State: {updated_job.state}")
            print(f"Sent at: {updated_job.sent_at}")
            print(f"Failure code: {updated_job.failure_code}")
            print(f"Safe metadata: {updated_job.safe_result_metadata}")
            if updated_job.state == "sent":
                print("\n>>> [SUCCESS] 消息已成功发送至买家 Mr. Mireille Sacrifice！")
                print(">>> 等待 3 秒后关闭浏览器...")
                await asyncio.sleep(3)
            else:
                print(f"\n>>> [NOTICE] 任务未处于 sent 状态: {updated_job.state} (code: {updated_job.failure_code})")
        else:
            print("No job processed by worker.")
    finally:
        await runtime.stop()
        await engine.dispose()

if __name__ == "__main__":
    asyncio.run(main())
