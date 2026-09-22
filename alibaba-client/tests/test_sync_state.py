import sqlite3

from alibaba_messenger.sync_state import SyncStateStore, read_status


def test_state_persists_completed_checkpoint_and_request_result(tmp_path):
    path = tmp_path / "sync.db"
    store = SyncStateStore(path)
    job = store.get_or_create_active_job("backfill", "default")
    store.mark_conversation_started(job, "139")
    store.record_batch(job, "139", 1, "req-1", {"createdMessages": 100})
    store.mark_conversation_complete(job, "139")
    store.close()

    restored = SyncStateStore(path)
    assert restored.resume_point(job).completed_inquiries == {"139"}
    assert restored.get_request_result("req-1")["createdMessages"] == 100
    restored.close()


def test_state_schema_has_no_sensitive_payload_columns(tmp_path):
    store = SyncStateStore(tmp_path / "sync.db")
    columns = [
        row[1].lower()
        for table in ("sync_job", "conversation_checkpoint", "request_result")
        for row in store.connection.execute(f"PRAGMA table_info({table})")
    ]
    assert not {"body", "content", "cookie", "token", "html"}.intersection(columns)
    store.close()


def test_read_status_does_not_create_a_missing_database(tmp_path):
    path = tmp_path / "missing.db"
    assert read_status(path) == {}
    assert not path.exists()


def test_tracked_conversation_and_change_detection(tmp_path):
    store = SyncStateStore(tmp_path / "sync.db")
    # 1. Unseen conversation is changed
    assert store.is_conversation_changed("inq-1", "hello", "2026-09-22 10:00", 0) is True

    # 2. Save conversation
    store.save_tracked_conversation("inq-1", "Alice", "hello", "2026-09-22 10:00", 0)
    tracked = store.get_tracked_conversation("inq-1")
    assert tracked is not None
    assert tracked["buyer_name"] == "Alice"
    assert tracked["last_message"] == "hello"

    # 3. Same state is not changed
    assert store.is_conversation_changed("inq-1", "hello", "2026-09-22 10:00", 0) is False

    # 4. Message changed
    assert store.is_conversation_changed("inq-1", "new message", "2026-09-22 10:00", 0) is True

    # 5. Time changed
    assert store.is_conversation_changed("inq-1", "hello", "2026-09-22 11:00", 0) is True

    # 6. Unread count > 0 is changed
    assert store.is_conversation_changed("inq-1", "hello", "2026-09-22 10:00", 1) is True

    store.close()
