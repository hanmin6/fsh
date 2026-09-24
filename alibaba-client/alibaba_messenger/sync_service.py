"""Backfill-only orchestration. No daemon or outbound behavior belongs here."""
from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass

from alibaba_messenger.crm_gateway import CrmPermanentError, CrmTransientError
from alibaba_messenger.sync_models import build_conversation_payload


def chunked(items, size):
    return [items[index:index + size] for index in range(0, len(items), size)]


def stable_request_id(job_id: str, inquiry_id: str, batch_no: int) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"{job_id}:{inquiry_id}:{batch_no}"))


def build_sync_payload(*, job_id, request_id, account_handle, conversation, messages, batch_no, final_batch, sync_mode="backfill"):
    return {"agentKey": "header-authenticated", "requestId": request_id, "accountHandle": account_handle,
            "syncMode": sync_mode, "jobId": job_id, "batchNo": batch_no, "finalBatch": final_batch,
            "conversation": build_conversation_payload(conversation),
            "messages": [message.model_dump(mode="json", by_alias=True) for message in messages]}


@dataclass
class SyncSummary:
    job_id: str
    mode: str = "backfill"
    completed: int = 0
    failed: int = 0
    skipped: int = 0


class AlibabaSyncService:
    def __init__(self, bot, gateway, state_store, settings, sleeper=asyncio.sleep):
        self.bot, self.gateway, self.state_store, self.settings, self.sleeper = bot, gateway, state_store, settings, sleeper

    async def _push_with_retry(self, payload, request_id):
        for attempt, delay in enumerate((1, 2, 4), start=1):
            try:
                return self.gateway.sync_batch(payload, request_id)
            except CrmTransientError:
                if attempt == 3: raise
                await self.sleeper(delay)
        raise AssertionError("unreachable")

    async def run_backfill(self) -> SyncSummary:
        job_id = self.state_store.get_or_create_active_job("backfill", self.settings.ACCOUNT_HANDLE)
        completed = self.state_store.resume_point(job_id).completed_inquiries
        summary = SyncSummary(job_id=job_id, mode="backfill")

        async def _iterate_conversations():
            if hasattr(self.bot, "iter_conversations_pages"):
                async for page_conversations in self.bot.iter_conversations_pages(max_pages=self.settings.BACKFILL_MAX_PAGES):
                    for conv in page_conversations:
                        yield conv
            else:
                for conv in await self.bot.get_all_conversations(max_pages=self.settings.BACKFILL_MAX_PAGES):
                    yield conv

        async for conversation in _iterate_conversations():
            inquiry_id = str(conversation["inquiry_id"])
            buyer_name = conversation.get("buyer_name") or "Unknown"
            if inquiry_id in completed:
                summary.skipped += 1
                continue
            self.state_store.mark_conversation_started(job_id, inquiry_id)
            print("[Sync] 正在同步历史会话…")
            try:
                try:
                    messages = await self.bot.get_sync_history(inquiry_id, buyer_name=buyer_name)
                except TypeError:
                    messages = await self.bot.get_sync_history(inquiry_id)
                batches = chunked(messages, getattr(self.settings, "SYNC_BATCH_SIZE", 100)) or [[]]
                for batch_no, batch in enumerate(batches, start=1):
                    request_id = stable_request_id(job_id, inquiry_id, batch_no)
                    payload = build_sync_payload(job_id=job_id, request_id=request_id, account_handle=self.settings.ACCOUNT_HANDLE,
                        conversation=conversation, messages=batch, batch_no=batch_no, final_batch=batch_no == len(batches), sync_mode="backfill")
                    self.state_store.record_batch(job_id, inquiry_id, batch_no, request_id, await self._push_with_retry(payload, request_id))
                self.state_store.mark_conversation_complete(job_id, inquiry_id)
                if hasattr(self.state_store, "save_tracked_conversation"):
                    self.state_store.save_tracked_conversation(
                        inquiry_id,
                        buyer_name,
                        conversation.get("last_message", ""),
                        conversation.get("last_time", ""),
                        int(conversation.get("unread_count", 0)),
                    )
                summary.completed += 1
                print(f"[Sync] 会话同步完成 (共 {len(messages)} 条消息)")
            except CrmPermanentError as exc:
                self.state_store.mark_conversation_failed(job_id, inquiry_id, "permanent", "permanent_sync_error")
                summary.failed += 1
                print("[Sync] 会话同步失败，安全错误代码已保存，可重试")
            except CrmTransientError as exc:
                self.state_store.mark_conversation_failed(job_id, inquiry_id, "transient", "transient_sync_error")
                summary.failed += 1
                print("[Sync] 会话同步失败，安全错误代码已保存，可重试")
            except (RuntimeError, ValueError, KeyError):
                self.state_store.mark_conversation_failed(job_id, inquiry_id, "source_read_failed", "source_read_failed")
                summary.failed += 1
                print("[Sync] 源记录读取失败，可重试")
        if summary.failed == 0:
            self.state_store.complete_job(job_id)
        return summary

    async def run_incremental_once(self, max_pages: int = 1) -> SyncSummary:
        job_id = self.state_store.start_job("incremental", self.settings.ACCOUNT_HANDLE)
        summary = SyncSummary(job_id=job_id, mode="incremental")

        conversations = []
        if hasattr(self.bot, "get_recent_conversations"):
            res = await self.bot.get_recent_conversations(limit=100)
            if isinstance(res, dict) and res.get("success"):
                conversations = res.get("data", {}).get("conversations", [])
            elif isinstance(res, list):
                conversations = res
        elif hasattr(self.bot, "iter_conversations_pages"):
            async for page_items in self.bot.iter_conversations_pages(max_pages=max_pages):
                conversations.extend(page_items)
        elif hasattr(self.bot, "get_all_conversations"):
            conversations = await self.bot.get_all_conversations(max_pages=max_pages)

        seen_inquiries = set()
        for conversation in conversations:
            inquiry_id = str(conversation.get("inquiry_id") or "")
            if not inquiry_id or inquiry_id in seen_inquiries:
                continue
            seen_inquiries.add(inquiry_id)

            buyer_name = conversation.get("buyer_name") or "Unknown"
            last_message = conversation.get("last_message") or ""
            last_time = conversation.get("last_time") or ""
            unread_count = int(conversation.get("unread_count") or 0)

            is_changed = True
            if hasattr(self.state_store, "is_conversation_changed"):
                is_changed = self.state_store.is_conversation_changed(inquiry_id, last_message, last_time, unread_count)

            if not is_changed:
                summary.skipped += 1
                continue

            self.state_store.mark_conversation_started(job_id, inquiry_id)
            print("[Sync] [Incremental] 发现会话更新")
            try:
                try:
                    messages = await self.bot.get_sync_history(inquiry_id, buyer_name=buyer_name)
                except TypeError:
                    messages = await self.bot.get_sync_history(inquiry_id)
                batch_size = getattr(self.settings, "SYNC_BATCH_SIZE", 100)
                batches = chunked(messages, batch_size) or [[]]
                for batch_no, batch in enumerate(batches, start=1):
                    request_id = stable_request_id(job_id, inquiry_id, batch_no)
                    payload = build_sync_payload(
                        job_id=job_id,
                        request_id=request_id,
                        account_handle=self.settings.ACCOUNT_HANDLE,
                        conversation=conversation,
                        messages=batch,
                        batch_no=batch_no,
                        final_batch=batch_no == len(batches),
                        sync_mode="incremental"
                    )
                    res = await self._push_with_retry(payload, request_id)
                    self.state_store.record_batch(job_id, inquiry_id, batch_no, request_id, res)
                self.state_store.mark_conversation_complete(job_id, inquiry_id)
                if hasattr(self.state_store, "save_tracked_conversation"):
                    self.state_store.save_tracked_conversation(inquiry_id, buyer_name, last_message, last_time, unread_count)
                summary.completed += 1
                print(f"[Sync] [Incremental] 会话入库完成 (共 {len(messages)} 条消息)")
            except CrmPermanentError as exc:
                self.state_store.mark_conversation_failed(job_id, inquiry_id, "permanent", "permanent_sync_error")
                summary.failed += 1
                print("[Sync] 会话同步失败，安全错误代码已保存，可重试")
            except CrmTransientError as exc:
                self.state_store.mark_conversation_failed(job_id, inquiry_id, "transient", "transient_sync_error")
                summary.failed += 1
                print("[Sync] 会话同步失败，安全错误代码已保存，可重试")

            except (RuntimeError, ValueError, KeyError):
                self.state_store.mark_conversation_failed(job_id, inquiry_id, "source_read_failed", "source_read_failed")
                summary.failed += 1
                print("[Sync] 源记录读取失败，可重试")
        if summary.failed == 0:
            self.state_store.complete_job(job_id)
        return summary

    async def run_daemon(self, interval: int = 300, stop_event: asyncio.Event | None = None) -> None:
        print(f"[Daemon] 阿里国际站增量同步守护进程已启动，巡检间隔: {interval}秒")
        while not (stop_event and stop_event.is_set()):
            try:
                summary = await self.run_incremental_once()
                print(f"[Daemon] 轮询完成: updated={summary.completed}, skipped={summary.skipped}, failed={summary.failed}")
            except asyncio.CancelledError:
                print("[Daemon] 守护进程收到终止信号，正常退出。")
                raise
            except Exception as exc:
                print("[Daemon] 本轮增量轮询异常，等待下次重试")

            if stop_event and stop_event.is_set():
                break

            if stop_event:
                try:
                    await asyncio.wait_for(stop_event.wait(), timeout=interval)
                except (asyncio.TimeoutError, TimeoutError):
                    pass
            else:
                await self.sleeper(interval)
