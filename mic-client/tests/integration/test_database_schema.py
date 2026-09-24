from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from alembic.config import Config
from sqlalchemy import create_engine as create_sync_engine
from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import create_async_engine

from alembic import command
from mic_gateway.domain import JobState, MessageIntent, SourceConversation


def test_public_enum_values_are_stable() -> None:
    assert MessageIntent.HOLIDAY_WISH.value == "holiday_wish"
    assert JobState.UNCERTAIN.value == "uncertain"


def test_source_records_require_timezone_aware_timestamps() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        SourceConversation(
            source_id="conversation-1",
            buyer_reference="buyer-1",
            inquiry_subject="Question",
            unread=True,
            last_message_at=None,
            source_updated_at=datetime(2026, 9, 19, 12, 0),
            raw_snapshot={},
        )

    record = SourceConversation(
        source_id="conversation-1",
        buyer_reference="buyer-1",
        inquiry_subject="Question",
        unread=True,
        last_message_at=None,
        source_updated_at=datetime(2026, 9, 19, 12, 0, tzinfo=UTC),
        raw_snapshot={},
    )
    assert record.source_id == "conversation-1"


@pytest.mark.asyncio
async def test_initial_migration_creates_operational_tables(tmp_path: Path) -> None:
    database_path = tmp_path / "schema.db"
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", f"sqlite:///{database_path.as_posix()}")

    command.upgrade(config, "head")

    engine = create_async_engine(f"sqlite+aiosqlite:///{database_path.as_posix()}")
    async with engine.connect() as connection:
        names = set(await connection.run_sync(lambda conn: inspect(conn).get_table_names()))
    await engine.dispose()
    names.discard("alembic_version")

    assert names == {
        "api_keys",
        "orders",
        "order_lines",
        "conversations",
        "messages",
        "sync_checkpoints",
        "outbox_jobs",
        "audit_events",
        "runtime_status",
    }


def test_history_migration_preserves_inquiry_rows_as_incomplete(tmp_path: Path) -> None:
    database_path = tmp_path / "existing.db"
    database_url = f"sqlite:///{database_path.as_posix()}"
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", database_url)
    command.upgrade(config, "0001_initial")

    with create_sync_engine(database_url).begin() as connection:
        connection.execute(
            text(
                "INSERT INTO conversations "
                "(id, source_id, buyer_reference, inquiry_subject, unread, last_message_at, "
                "source_updated_at, synced_at, raw_snapshot) VALUES "
                "(:id, :source_id, :buyer, :subject, :unread, :last_message_at, "
                ":source_updated_at, :synced_at, :raw_snapshot)"
            ),
            {
                "id": "00000000-0000-0000-0000-000000000001",
                "source_id": "legacy-conversation",
                "buyer": "buyer-legacy",
                "subject": "Old inquiry",
                "unread": 0,
                "last_message_at": "2026-09-19 12:00:00",
                "source_updated_at": "2026-09-19 12:00:00",
                "synced_at": "2026-09-19 12:00:00",
                "raw_snapshot": "{}",
            },
        )
        connection.execute(
            text(
                "INSERT INTO outbox_jobs "
                "(id, idempotency_key, payload_digest, conversation_id, intent, content, "
                "caller_reference, caller_key_id, request_id, state, attempt_count, "
                "next_attempt_at, attempted_at, sent_at, failure_code, safe_result_metadata, "
                "created_at, updated_at) VALUES "
                "(:id, :key, :digest, :conversation_id, :intent, :content, NULL, NULL, "
                ":request_id, :state, :attempt_count, NULL, NULL, NULL, NULL, :metadata, "
                ":created_at, :updated_at)"
            ),
            {
                "id": "00000000-0000-0000-0000-000000000003",
                "key": "legacy-outbox-key",
                "digest": "b" * 64,
                "conversation_id": "00000000-0000-0000-0000-000000000001",
                "intent": "greeting",
                "content": "Approved message",
                "request_id": "legacy-request",
                "state": "sent",
                "attempt_count": 1,
                "metadata": "{}",
                "created_at": "2026-09-19 12:00:00",
                "updated_at": "2026-09-19 12:00:00",
            },
        )
        connection.execute(
            text(
                "INSERT INTO messages "
                "(id, source_id, fallback_fingerprint, conversation_id, direction, "
                "sender_label, content, attachment_metadata, source_created_at, synced_at, "
                "outbound_job_id, raw_snapshot) VALUES "
                "(:id, :source_id, :fingerprint, :conversation_id, :direction, :sender, "
                ":content, :attachments, :source_created_at, :synced_at, NULL, :raw_snapshot)"
            ),
            {
                "id": "00000000-0000-0000-0000-000000000002",
                "source_id": "legacy-inquiry",
                "fingerprint": "a" * 64,
                "conversation_id": "00000000-0000-0000-0000-000000000001",
                "direction": "inbound",
                "sender": "buyer-legacy",
                "content": "Existing inquiry body",
                "attachments": "[]",
                "source_created_at": "2026-09-19 12:00:00",
                "synced_at": "2026-09-19 12:00:00",
                "raw_snapshot": "{}",
            },
        )

    command.upgrade(config, "head")

    with create_sync_engine(database_url).connect() as connection:
        conversation = connection.execute(
            text(
                "SELECT source_id, history_complete FROM conversations "
                "WHERE source_id = 'legacy-conversation'"
            )
        ).one()
        message = connection.execute(
            text("SELECT source_id, content, source_sequence FROM messages")
        ).one()
        outbox_id = connection.execute(
            text("SELECT id FROM outbox_jobs WHERE idempotency_key = 'legacy-outbox-key'")
        ).scalar_one()
        tables = set(inspect(connection).get_table_names())

    assert conversation == ("legacy-conversation", 0)
    assert message == ("legacy-inquiry", "Existing inquiry body", None)
    assert outbox_id == "00000000-0000-0000-0000-000000000003"
    assert "outbox_jobs" in tables
