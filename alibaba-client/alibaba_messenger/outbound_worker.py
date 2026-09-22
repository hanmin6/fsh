# -*- coding: utf-8 -*-
"""Outbound dispatch worker and heartbeat reporter for CRM integration."""
from __future__ import annotations

import asyncio
import logging
import time
import uuid
from typing import Any

from alibaba_messenger.crm_gateway import CrmAuthError, CrmGateway, CrmPermanentError, CrmTransientError

logger = logging.getLogger("outbound_worker")


class OutboundWorker:
    """Consumes approved outbound tasks from CRM and synchronizes agent health."""

    def __init__(
        self,
        bot: Any,
        gateway: CrmGateway,
        settings: Any,
        sleeper: Any = asyncio.sleep,
        dry_run: bool = False,
    ):
        self.bot = bot
        self.gateway = gateway
        self.settings = settings
        self.sleeper = sleeper
        self.dry_run = dry_run
        self.last_heartbeat_at: float = 0.0

    async def send_heartbeat(self) -> bool:
        """Report execution agent status to CRM based on browser login state."""
        try:
            is_logged_in = getattr(self.bot, "is_logged_in", False)
            if is_logged_in:
                status = "online"
                last_error = None
            else:
                status = "offline"
                last_error = "Alibaba messenger session is not logged in"

            self.gateway.heartbeat(status=status, last_error=last_error)
            self.last_heartbeat_at = time.time()
            logger.info(f"[OutboundWorker] Heartbeat sent: status={status}")
            return True
        except (CrmTransientError, CrmAuthError, CrmPermanentError) as exc:
            logger.warning(f"[OutboundWorker] Failed to send heartbeat to CRM: {exc}")
            return False
        except Exception as exc:
            logger.error(f"[OutboundWorker] Unexpected error sending heartbeat: {exc}")
            return False

    async def process_one_task(self, task: dict) -> bool:
        """Execute a single claimed OutboundTask and report result to CRM."""
        task_id = str(task.get("id") or "")
        inquiry_id = str(task.get("inquiryId") or "")
        buyer_name = str(task.get("buyerName") or "")
        body = str(task.get("body") or "")
        mode = str(task.get("executionMode") or "real")

        logger.info(f"[OutboundWorker] Processing task {task_id} (mode={mode}, inquiry={inquiry_id}, buyer={buyer_name})")

        # 1. Mark task as sending in CRM
        try:
            self.gateway.mark_sending(task_id)
        except Exception as exc:
            logger.error(f"[OutboundWorker] Failed to mark task {task_id} as sending: {exc}")
            return False

        # 2. Simulated or Dry-run send
        if mode == "mock" or self.dry_run:
            prefix = "DRYRUN" if self.dry_run else "MOCK"
            receipt_id = f"{prefix}-OUT-{uuid.uuid4().hex[:12]}"
            logger.info(f"[OutboundWorker] Task {task_id} simulated send successful: receipt={receipt_id}")
            self.gateway.report_result(
                task_id=task_id,
                success=True,
                platform_message_id=receipt_id,
            )
            return True

        # 3. Real send via AlibabaMessengerBot
        effective_target = buyer_name or inquiry_id or "unknown"
        try:
            res = await self.bot.send_message(
                buyer_name=effective_target,
                message=body,
                inquiry_id=inquiry_id,
            )
            success = bool(res.get("success", False))
            if success:
                platform_message_id = (
                    res.get("data", {}).get("sent_at")
                    or f"ALI-MSG-{int(time.time())}"
                )
                logger.info(f"[OutboundWorker] Task {task_id} sent successfully to {effective_target}")
                self.gateway.report_result(
                    task_id=task_id,
                    success=True,
                    platform_message_id=platform_message_id,
                    error_message=None,
                )
                return True
            else:
                error_msg = res.get("message") or "Unknown bot execution failure"
                logger.warning(f"[OutboundWorker] Task {task_id} send failed: {error_msg}")
                self.gateway.report_result(
                    task_id=task_id,
                    success=False,
                    platform_message_id=None,
                    error_message=error_msg,
                )
                return False
        except Exception as exc:
            logger.exception(f"[OutboundWorker] Exception during bot.send_message for task {task_id}: {exc}")
            try:
                self.gateway.report_result(
                    task_id=task_id,
                    success=False,
                    platform_message_id=None,
                    error_message=f"Exception: {str(exc)}",
                )
            except Exception:
                pass
            return False

    async def poll_and_execute_once(self) -> bool:
        """Poll CRM for one pending outbound task and process it."""
        try:
            claim_res = self.gateway.claim()
        except (CrmTransientError, CrmAuthError, CrmPermanentError) as exc:
            logger.warning(f"[OutboundWorker] Failed to claim task from CRM: {exc}")
            return False
        except Exception as exc:
            logger.error(f"[OutboundWorker] Unexpected claim error: {exc}")
            return False

        if claim_res.get("paused", False):
            logger.info("[OutboundWorker] CRM Outbound is paused (FUSANHE_OUTBOUND_PAUSED=true). In cooling-down state.")
            return False

        task = claim_res.get("task")
        if not task:
            return False

        return await self.process_one_task(task)

    async def run_loop(
        self,
        stop_event: asyncio.Event | None = None,
        poll_interval: float = 15.0,
        heartbeat_interval: float = 60.0,
    ) -> None:
        """Continuous execution loop coordinating heartbeats and task polling."""
        stop = stop_event or asyncio.Event()
        logger.info("[OutboundWorker] Worker loop started.")

        # Initial heartbeat
        await self.send_heartbeat()

        while not stop.is_set():
            now = time.time()
            if now - self.last_heartbeat_at >= heartbeat_interval:
                await self.send_heartbeat()

            task_processed = await self.poll_and_execute_once()

            if task_processed:
                # If a task was processed, short sleep to handle back-to-back tasks quickly
                await self.sleeper(1.0)
            else:
                # Wait for poll_interval, checking stop event
                try:
                    await asyncio.wait_for(stop.wait(), timeout=poll_interval)
                except asyncio.TimeoutError:
                    pass

        logger.info("[OutboundWorker] Worker loop stopped.")
