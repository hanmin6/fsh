"""Minimal resumable state; intentionally never persists source message bodies."""
from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class ResumePoint:
    completed_inquiries: set[str]


class SyncStateStore:
    def __init__(self, path: str | Path):
        self.connection = sqlite3.connect(str(path))
        self.connection.execute("PRAGMA journal_mode=WAL")
        self.connection.execute("PRAGMA foreign_keys=ON")
        self._create_schema()

    def _create_schema(self) -> None:
        with self.connection:
            self.connection.executescript("""
                CREATE TABLE IF NOT EXISTS sync_job (
                    job_id TEXT PRIMARY KEY, mode TEXT NOT NULL, account_handle TEXT NOT NULL,
                    status TEXT NOT NULL, started_at TEXT NOT NULL, completed_at TEXT
                );
                CREATE TABLE IF NOT EXISTS conversation_checkpoint (
                    job_id TEXT NOT NULL, inquiry_id TEXT NOT NULL, status TEXT NOT NULL,
                    error_code TEXT, error_message TEXT, updated_at TEXT NOT NULL,
                    PRIMARY KEY (job_id, inquiry_id), FOREIGN KEY (job_id) REFERENCES sync_job(job_id)
                );
                CREATE TABLE IF NOT EXISTS request_result (
                    request_id TEXT PRIMARY KEY, job_id TEXT NOT NULL, inquiry_id TEXT NOT NULL,
                    batch_no INTEGER NOT NULL, result_json TEXT NOT NULL, created_at TEXT NOT NULL,
                    FOREIGN KEY (job_id) REFERENCES sync_job(job_id)
                );
                CREATE TABLE IF NOT EXISTS tracked_conversation (
                    inquiry_id TEXT PRIMARY KEY, buyer_name TEXT,
                    last_message TEXT, last_time TEXT, unread_count INTEGER DEFAULT 0,
                    last_synced_at TEXT NOT NULL
                );
            """)

    def start_job(self, mode: str, account_handle: str) -> str:
        job_id = str(uuid4())
        with self.connection:
            self.connection.execute("INSERT INTO sync_job VALUES (?, ?, ?, 'running', ?, NULL)", (job_id, mode, account_handle, _now()))
        return job_id

    def get_or_create_active_job(self, mode: str, account_handle: str) -> str:
        row = self.connection.execute(
            "SELECT job_id FROM sync_job WHERE mode=? AND account_handle=? AND status='running' ORDER BY started_at DESC LIMIT 1",
            (mode, account_handle),
        ).fetchone()
        return row[0] if row else self.start_job(mode, account_handle)

    def _checkpoint(self, job_id: str, inquiry_id: str, status: str, error_code: str | None = None, error_message: str | None = None) -> None:
        with self.connection:
            self.connection.execute("""INSERT INTO conversation_checkpoint VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(job_id, inquiry_id) DO UPDATE SET status=excluded.status, error_code=excluded.error_code,
                error_message=excluded.error_message, updated_at=excluded.updated_at""", (job_id, inquiry_id, status, error_code, error_message, _now()))

    def mark_conversation_started(self, job_id: str, inquiry_id: str) -> None: self._checkpoint(job_id, inquiry_id, "started")
    def mark_conversation_complete(self, job_id: str, inquiry_id: str) -> None: self._checkpoint(job_id, inquiry_id, "completed")
    def mark_conversation_failed(self, job_id: str, inquiry_id: str, error_code: str, error_message: str) -> None: self._checkpoint(job_id, inquiry_id, "failed", error_code, error_message[:500])

    def record_batch(self, job_id: str, inquiry_id: str, batch_no: int, request_id: str, result: dict) -> None:
        def redact(value):
            if isinstance(value, dict):
                return {key: redact(item) for key, item in value.items()
                        if key.lower() not in {"body", "content", "message", "messages", "token", "cookie", "headers", "html"}}
            if isinstance(value, list):
                return [redact(item) for item in value]
            return value
        safe = redact(result)
        with self.connection:
            self.connection.execute("INSERT OR REPLACE INTO request_result VALUES (?, ?, ?, ?, ?, ?)", (request_id, job_id, inquiry_id, batch_no, json.dumps(safe), _now()))

    def resume_point(self, job_id: str) -> ResumePoint:
        rows = self.connection.execute("SELECT inquiry_id FROM conversation_checkpoint WHERE job_id=? AND status='completed'", (job_id,)).fetchall()
        return ResumePoint({row[0] for row in rows})

    def get_request_result(self, request_id: str) -> dict | None:
        row = self.connection.execute("SELECT result_json FROM request_result WHERE request_id=?", (request_id,)).fetchone()
        return json.loads(row[0]) if row else None

    def last_success_at(self) -> str | None:
        row = self.connection.execute("SELECT MAX(completed_at) FROM sync_job WHERE status='completed'").fetchone()
        return row[0]

    def complete_job(self, job_id: str) -> None:
        with self.connection:
            self.connection.execute("UPDATE sync_job SET status='completed', completed_at=? WHERE job_id=?", (_now(), job_id))

    def status(self) -> dict:
        rows = self.connection.execute("SELECT status, COUNT(*) FROM sync_job GROUP BY status").fetchall()
        return {status: count for status, count in rows}

    def get_tracked_conversation(self, inquiry_id: str) -> dict | None:
        row = self.connection.execute(
            "SELECT inquiry_id, buyer_name, last_message, last_time, unread_count, last_synced_at FROM tracked_conversation WHERE inquiry_id=?",
            (str(inquiry_id),)
        ).fetchone()
        if not row:
            return None
        return {
            "inquiry_id": row[0],
            "buyer_name": row[1],
            "last_message": row[2],
            "last_time": row[3],
            "unread_count": row[4],
            "last_synced_at": row[5],
        }

    def save_tracked_conversation(
        self,
        inquiry_id: str,
        buyer_name: str,
        last_message: str,
        last_time: str,
        unread_count: int = 0
    ) -> None:
        with self.connection:
            self.connection.execute(
                """INSERT INTO tracked_conversation (inquiry_id, buyer_name, last_message, last_time, unread_count, last_synced_at)
                   VALUES (?, ?, ?, ?, ?, ?)
                   ON CONFLICT(inquiry_id) DO UPDATE SET
                       buyer_name=excluded.buyer_name,
                       last_message=excluded.last_message,
                       last_time=excluded.last_time,
                       unread_count=excluded.unread_count,
                       last_synced_at=excluded.last_synced_at""",
                (str(inquiry_id), buyer_name, last_message, last_time, int(unread_count), _now())
            )

    def is_conversation_changed(
        self,
        inquiry_id: str,
        last_message: str,
        last_time: str,
        unread_count: int = 0
    ) -> bool:
        tracked = self.get_tracked_conversation(str(inquiry_id))
        if tracked is None:
            return True
        if unread_count > 0:
            return True
        if (last_message or "").strip() != (tracked["last_message"] or "").strip():
            return True
        if (last_time or "").strip() != (tracked["last_time"] or "").strip():
            return True
        return False

    def close(self) -> None: self.connection.close()


def read_status(path: str | Path) -> dict:
    """Read existing state without schema creation, WAL configuration, or browser setup."""
    target = Path(path)
    if not target.exists():
        return {}
    connection = sqlite3.connect(f"file:{target.absolute().as_posix()}?mode=ro", uri=True)
    try:
        return {status: count for status, count in connection.execute("SELECT status, COUNT(*) FROM sync_job GROUP BY status")}
    finally:
        connection.close()
