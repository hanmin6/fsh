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




def test_failed_backfill_keeps_job_resumable_and_redacts_logs(tmp_path, capsys):
    from alibaba_messenger.sync_state import SyncStateStore
    from alibaba_messenger.crm_gateway import CrmTransientError

    class FailingGateway:
        def sync_batch(self, *args):
            raise CrmTransientError('private-token-and-customer-text')

    async def no_sleep(_): pass
    store = SyncStateStore(tmp_path / 'sync.db')
    summary = asyncio.run(AlibabaSyncService(FakeBot(), FailingGateway(), store, Settings(), sleeper=no_sleep).run_backfill())
    assert summary.failed == 1
    assert store.status() == {'running': 1}
    assert store.get_or_create_active_job('backfill', 'default') == summary.job_id
    assert 'private-token-and-customer-text' not in capsys.readouterr().out
    error = store.connection.execute('SELECT error_message FROM conversation_checkpoint').fetchone()[0]
    assert error == 'transient_sync_error'
    store.close()


def test_sync_service_backfills_country_from_bot_cache():
    class CacheBot:
        def __init__(self):
            self.countries = {"inq-99": "Malaysia"}

        async def iter_conversations_pages(self, max_pages=1000):
            # Country is empty initially from list
            yield [{"inquiry_id": "inq-99", "buyer_name": "Rahman", "country": "", "create_time": "", "last_time": ""}]

        async def get_sync_history(self, inquiry_id, buyer_name=None):
            return [SyncMessage.from_source(inquiry_id, "buyer", "Salam", "2026-09-24 10:00", 1, None, "chat")]

        def get_last_extracted_country(self, inquiry_id):
            return self.countries.get(str(inquiry_id), "")

    gateway, state = FakeGateway(), FakeState()
    summary = asyncio.run(AlibabaSyncService(CacheBot(), gateway, state, Settings()).run_backfill())
    assert summary.completed == 1
    assert len(gateway.calls) == 1
    # Country must be backfilled into the conversation payload sent to CRM
    assert gateway.calls[0][0]["conversation"]["country"] == "Malaysia"


def test_incremental_sync_invokes_auto_refresh():
    """验证 run_incremental_once 默认传递 auto_refresh=True 以主动刷新商机列表"""
    class RefreshTrackingBot:
        def __init__(self):
            self.auto_refresh_passed = None

        async def get_recent_conversations(self, limit=100, auto_refresh=False):
            self.auto_refresh_passed = auto_refresh
            return {"success": True, "data": {"conversations": []}}

    bot = RefreshTrackingBot()
    state = FakeState()
    state.start_job = lambda *a: "job-refresh"
    service = AlibabaSyncService(bot, FakeGateway(), state, Settings())
    asyncio.run(service.run_incremental_once())
    assert bot.auto_refresh_passed is True


def test_daemon_invokes_keep_alive_and_recovers_from_error():
    """验证 run_daemon 循环中主动触发 bot.keep_alive 并具备异常容错"""
    class KeepAliveBot:
        def __init__(self):
            self.keep_alive_called = 0

        async def keep_alive(self, max_idle_seconds=300):
            self.keep_alive_called += 1
            return True

        async def get_recent_conversations(self, limit=100, auto_refresh=False):
            # 首次触发异常，模拟网络或页面偶发错误
            if self.keep_alive_called == 1:
                raise RuntimeError("transient page error")
            return {"success": True, "data": {"conversations": []}}

    bot = KeepAliveBot()
    state = FakeState()
    state.start_job = lambda *a: "job-daemon"
    service = AlibabaSyncService(bot, FakeGateway(), state, Settings())

    stop_event = asyncio.Event()

    async def _test():
        # run daemon once with error, then stop
        loop_task = asyncio.create_task(service.run_daemon(interval=1, stop_event=stop_event))
        await asyncio.sleep(0.05)
        stop_event.set()
        await loop_task

    asyncio.run(_test())
    assert bot.keep_alive_called >= 1

