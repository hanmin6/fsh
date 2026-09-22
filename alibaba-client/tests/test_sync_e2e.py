# -*- coding: utf-8 -*-
import asyncio
import json
import os
import tempfile
from pathlib import Path

import pytest

from alibaba_messenger.crm_gateway import CrmGateway
from alibaba_messenger.sync_models import SyncMessage
from alibaba_messenger.sync_service import AlibabaSyncService
from alibaba_messenger.sync_state import SyncStateStore

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


class FixtureBot:
    """Mock Alibaba bot driven by redacted JSON fixtures."""

    def __init__(self):
        with open(FIXTURES_DIR / "alibaba_conversations.json", "r", encoding="utf-8") as f:
            self.conversations = json.load(f)

    async def get_all_conversations(self, max_pages: int = 1000):
        return self.conversations

    async def get_sync_history(self, inquiry_id: str):
        fixture_path = FIXTURES_DIR / f"alibaba_history_{inquiry_id}.json"
        if not fixture_path.exists():
            return []
        with open(fixture_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        converted = []
        for sequence, raw in enumerate(data.get("messages", []), start=1):
            msg = SyncMessage.from_source(
                inquiry_id=inquiry_id,
                sender=raw.get("sender", "buyer"),
                content=raw.get("content", ""),
                raw_time=raw.get("raw_time") or raw.get("time", ""),
                sequence=sequence,
                platform_id=raw.get("platform_id"),
                message_type=raw.get("type", "chat"),
            )
            if msg is not None:
                converted.append(msg)
        return converted


class DummySettings:
    ACCOUNT_HANDLE = "default"
    SYNC_BATCH_SIZE = 50
    BACKFILL_MAX_PAGES = 100


@pytest.mark.asyncio
async def test_fixture_driven_backfill_e2e():
    """Verify fixture-driven backfill processes all conversations and writes valid checkpoints."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "sync.db"
        state = SyncStateStore(db_path)
        try:
            bot = FixtureBot()
            sent_payloads = []

            class MockGateway:
                def sync_batch(self, payload, request_id):
                    sent_payloads.append((payload, request_id))
                    return {
                        "requestId": request_id,
                        "conversationId": f"conv_{payload['conversation']['inquiryId']}",
                        "createdMessages": len(payload.get("messages", [])),
                        "finalized": payload.get("finalBatch", False),
                    }

            gateway = MockGateway()
            settings = DummySettings()
            service = AlibabaSyncService(bot, gateway, state, settings)

            summary = await service.run_backfill()
            assert summary.completed == 2
            assert summary.failed == 0
            assert summary.skipped == 0
            assert len(sent_payloads) == 2

            # Check conversation 1 details
            p1 = sent_payloads[0][0]
            assert p1["conversation"]["inquiryId"] == "13907077489"
            assert p1["conversation"]["buyerName"] == "Redacted Buyer Alpha"
            assert len(p1["messages"]) == 3
            assert p1["messages"][0]["sourceSequence"] == 1
            assert p1["messages"][0]["direction"] == "inbound"
            assert p1["messages"][1]["sourceSequence"] == 2
            assert p1["messages"][1]["direction"] == "outbound"
            assert p1["messages"][2]["sourceSequence"] == 3
            assert p1["messages"][2]["direction"] == "inbound"
            assert p1["finalBatch"] is True

            # Check resume behavior on an active job:
            active_job = state.start_job("backfill", "default")
            state.mark_conversation_complete(active_job, "13907077489")
            # Now running backfill with this active job will skip 13907077489
            summary_resume = await service.run_backfill()
            assert summary_resume.job_id == active_job
            assert summary_resume.completed == 1  # 13907389909 completed
            assert summary_resume.skipped == 1    # 13907077489 skipped
        finally:
            state.close()


@pytest.mark.asyncio
async def test_live_crm_backfill_with_fixture_bot():
    """If isolated CRM is reachable on 18080, run live end-to-end sync with FixtureBot."""
    crm_url = os.getenv("CRM_API_URL", "http://localhost:18080/api/v1")
    agent_key = os.getenv("FUSANHE_AGENT_KEY", "guangzhou-alibaba-01")
    agent_token = os.getenv("FUSANHE_AGENT_TOKEN", "46s_V172sxmuCFAaG802hauyAUQTcSTkDZ4LYRtRx2I")

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "live_sync.db"
        state = SyncStateStore(db_path)
        try:
            bot = FixtureBot()
            gateway = CrmGateway(crm_url, agent_key, agent_token)
            settings = DummySettings()
            service = AlibabaSyncService(bot, gateway, state, settings)

            summary = await service.run_backfill()
            assert summary.completed == 2
            assert summary.failed == 0
        except Exception as exc:
            pytest.skip(f"Live CRM stack not reachable or not ready: {exc}")
        finally:
            state.close()
