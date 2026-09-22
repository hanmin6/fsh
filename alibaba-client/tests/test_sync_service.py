import asyncio

from alibaba_messenger.sync_models import SyncMessage
from alibaba_messenger.sync_service import AlibabaSyncService


class FakeBot:
    async def get_all_conversations(self, max_pages=1000):
        return [{"inquiry_id": "1", "buyer_name": "", "country": "", "create_time": "", "last_time": ""}]

    async def get_sync_history(self, inquiry_id):
        return [SyncMessage.from_source(inquiry_id, "buyer", "one", "2026-09-21 10:00", 1, None, "chat")] * 101


class FakeGateway:
    def __init__(self): self.calls = []
    def sync_batch(self, payload, request_id): self.calls.append((payload, request_id)); return {"ok": True}


class FakeState:
    def __init__(self): self.completed = set(); self.recorded = []
    def get_or_create_active_job(self, mode, account): return "job"
    def resume_point(self, job): return type("Resume", (), {"completed_inquiries": self.completed})()
    def mark_conversation_started(self, *args): pass
    def record_batch(self, *args): self.recorded.append(args)
    def mark_conversation_complete(self, _, inquiry): self.completed.add(inquiry)
    def mark_conversation_failed(self, *args): raise AssertionError(args)
    def complete_job(self, *args): pass


class Settings:
    ACCOUNT_HANDLE = "default"
    SYNC_BATCH_SIZE = 100
    BACKFILL_MAX_PAGES = 1000


def test_backfill_batches_history_and_uses_fallback_buyer_name():
    gateway, state = FakeGateway(), FakeState()
    summary = asyncio.run(AlibabaSyncService(FakeBot(), gateway, state, Settings()).run_backfill())
    assert summary.completed == 1
    assert len(gateway.calls) == 2
    assert gateway.calls[0][0]["finalBatch"] is False
    assert gateway.calls[1][0]["finalBatch"] is True
    assert gateway.calls[0][0]["conversation"]["buyerName"] == "Alibaba Buyer 1"


def test_completed_conversation_is_skipped_on_resume():
    gateway, state = FakeGateway(), FakeState()
    state.completed.add("1")
    summary = asyncio.run(AlibabaSyncService(FakeBot(), gateway, state, Settings()).run_backfill())
    assert (summary.skipped, len(gateway.calls)) == (1, 0)


def test_backfill_with_paged_conversations_streaming():
    class PagedBot:
        async def iter_conversations_pages(self, max_pages=1000):
            yield [{"inquiry_id": "1", "buyer_name": "Gleb Cherenkov", "country": "RU", "create_time": "", "last_time": ""}]
            yield [{"inquiry_id": "2", "buyer_name": "Alice", "country": "US", "create_time": "", "last_time": ""}]

        async def get_sync_history(self, inquiry_id, buyer_name=None):
            return [SyncMessage.from_source(inquiry_id, "buyer", "hello", "2026-09-22 10:00", 1, None, "chat")]

    gateway, state = FakeGateway(), FakeState()
    summary = asyncio.run(AlibabaSyncService(PagedBot(), gateway, state, Settings()).run_backfill())
    assert summary.completed == 2
    assert len(gateway.calls) == 2
    assert gateway.calls[0][0]["conversation"]["buyerName"] == "Gleb Cherenkov"
    assert gateway.calls[1][0]["conversation"]["buyerName"] == "Alice"


def test_incremental_sync_skips_unchanged_and_syncs_changed():
    class RecentBot:
        async def get_recent_conversations(self, limit=100):
            return {
                "success": True,
                "data": {
                    "conversations": [
                        {"inquiry_id": "1", "buyer_name": "Alice", "last_message": "old message", "last_time": "2026-09-22 09:00", "unread_count": 0},
                        {"inquiry_id": "2", "buyer_name": "Bob", "last_message": "new order inquiry", "last_time": "2026-09-22 10:30", "unread_count": 1},
                    ]
                }
            }

        async def get_sync_history(self, inquiry_id, buyer_name=None):
            return [SyncMessage.from_source(inquiry_id, "buyer", "hi", "2026-09-22 10:30", 1, None, "chat")]

    class FakeIncrementalState:
        def __init__(self, changed_ids):
            self.changed_ids = set(changed_ids)
            self.tracked = {}
            self.completed = []
            self.recorded = []

        def start_job(self, mode, account): return "job-inc"
        def mark_conversation_started(self, *args): pass
        def is_conversation_changed(self, inquiry_id, last_message, last_time, unread_count=0):
            return inquiry_id in self.changed_ids
        def save_tracked_conversation(self, inquiry_id, buyer_name, last_message, last_time, unread_count=0):
            self.tracked[inquiry_id] = (buyer_name, last_message, unread_count)
        def record_batch(self, *args): self.recorded.append(args)
        def mark_conversation_complete(self, _, inquiry): self.completed.append(inquiry)
        def complete_job(self, *args): pass

    gateway = FakeGateway()
    state = FakeIncrementalState(changed_ids=["2"])  # Only inquiry 2 changed
    service = AlibabaSyncService(RecentBot(), gateway, state, Settings())
    summary = asyncio.run(service.run_incremental_once())

    assert summary.completed == 1
    assert summary.skipped == 1
    assert len(gateway.calls) == 1
    payload, _ = gateway.calls[0]
    assert payload["syncMode"] == "incremental"
    assert payload["conversation"]["inquiryId"] == "2"
    assert state.completed == ["2"]
    assert "2" in state.tracked
    assert state.tracked["2"][0] == "Bob"


def test_daemon_runs_and_respects_stop_event():
    class EmptyRecentBot:
        async def get_recent_conversations(self, limit=100):
            return {"success": True, "data": {"conversations": []}}

    class FakeDaemonState:
        def start_job(self, *args): return "d-job"
        def complete_job(self, *args): pass

    stop_event = asyncio.Event()

    async def _run():
        service = AlibabaSyncService(EmptyRecentBot(), FakeGateway(), FakeDaemonState(), Settings())
        # Set stop_event before next sleep
        stop_event.set()
        await service.run_daemon(interval=1, stop_event=stop_event)

    asyncio.run(_run())


