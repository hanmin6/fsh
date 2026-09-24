from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path
from typing import Any

from mic_gateway.crm_bridge.crm_client import CrmSyncResult, _is_confirmed_sync_response


class CrmBridgeState:
    """SQLite checkpoint journal; stores cursors and hashes, never credentials or payloads."""

    def __init__(self, app_data_dir: Path | str) -> None:
        self.directory = Path(app_data_dir).expanduser().resolve() / "crm-bridge"
        self.directory.mkdir(parents=True, exist_ok=True)
        self.path = self.directory / "checkpoints.sqlite3"
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS checkpoints (
                    resource TEXT PRIMARY KEY,
                    cursor TEXT,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS pending_batches (
                    resource TEXT PRIMARY KEY,
                    start_cursor TEXT,
                    next_cursor TEXT,
                    request_id TEXT NOT NULL,
                    payload_sha256 TEXT NOT NULL,
                    conflict INTEGER NOT NULL DEFAULT 0,
                    FOREIGN KEY(resource) REFERENCES checkpoints(resource)
                );
                CREATE TABLE IF NOT EXISTS manual_resolutions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    resource TEXT NOT NULL,
                    request_id TEXT NOT NULL,
                    resolution TEXT NOT NULL,
                    resolved_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS outbound_jobs (
                    task_id TEXT PRIMARY KEY,
                    source_id TEXT NOT NULL,
                    gateway_job_id TEXT,
                    idempotency_key TEXT NOT NULL UNIQUE,
                    status TEXT NOT NULL,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                """
            )
            columns = {row[1] for row in self._connect_columns(connection, "pending_batches")}
            if "conflict" not in columns:
                connection.execute(
                    "ALTER TABLE pending_batches ADD COLUMN conflict INTEGER NOT NULL DEFAULT 0"
                )

    def prepare_outbound_job(self, task_id: str, source_id: str, idempotency_key: str) -> None:
        """Record a CRM task before submit without persisting its message body."""
        with self._connect() as connection:
            row = connection.execute(
                "SELECT source_id, idempotency_key FROM outbound_jobs WHERE task_id = ?",
                (task_id,),
            ).fetchone()
            if row is not None and tuple(row) != (source_id, idempotency_key):
                raise ValueError("CRM task already has a different outbound identity")
            connection.execute(
                "INSERT OR IGNORE INTO outbound_jobs "
                "(task_id, source_id, idempotency_key, status) VALUES (?, ?, ?, 'submitting')",
                (task_id, source_id, idempotency_key),
            )

    def set_outbound_gateway_job(self, task_id: str, gateway_job_id: str) -> None:
        if not gateway_job_id.strip():
            raise ValueError("gateway job ID is required")
        with self._connect() as connection:
            row = connection.execute(
                "SELECT gateway_job_id FROM outbound_jobs WHERE task_id = ?", (task_id,)
            ).fetchone()
            if row is None:
                raise ValueError("outbound task was not prepared")
            if row[0] is not None and row[0] != gateway_job_id:
                raise ValueError("CRM task is already linked to a different gateway job")
            connection.execute(
                "UPDATE outbound_jobs SET gateway_job_id = ?, status = 'queued', "
                "updated_at = CURRENT_TIMESTAMP WHERE task_id = ?",
                (gateway_job_id, task_id),
            )

    def outbound_jobs(self) -> list[dict[str, str | None]]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT task_id, source_id, gateway_job_id, idempotency_key, status "
                "FROM outbound_jobs ORDER BY updated_at, task_id"
            ).fetchall()
        return [
            {
                "task_id": row[0],
                "source_id": row[1],
                "gateway_job_id": row[2],
                "idempotency_key": row[3],
                "status": row[4],
            }
            for row in rows
        ]

    def update_outbound_status(self, task_id: str, status: str) -> None:
        allowed = {"submitting", "queued", "sending", "uncertain", "requires_human_review"}
        if status not in allowed:
            raise ValueError("unsupported outbound status")
        with self._connect() as connection:
            cursor = connection.execute(
                "UPDATE outbound_jobs SET status = ?, updated_at = CURRENT_TIMESTAMP "
                "WHERE task_id = ?",
                (status, task_id),
            )
            if cursor.rowcount != 1:
                raise ValueError("outbound task was not prepared")

    def remove_outbound_job(self, task_id: str) -> None:
        with self._connect() as connection:
            connection.execute("DELETE FROM outbound_jobs WHERE task_id = ?", (task_id,))

    def checkpoint(self, resource: str) -> str | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT cursor FROM checkpoints WHERE resource = ?", (resource,)
            ).fetchone()
        return row[0] if row else None

    def stage_batch(
        self,
        resource: str,
        *,
        start_cursor: str | None,
        next_cursor: str | None,
        request_id: str,
        payload: dict[str, Any],
    ) -> None:
        digest = hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode(
                "utf-8"
            )
        ).hexdigest()
        with self._connect() as connection:
            connection.execute(
                "INSERT OR IGNORE INTO checkpoints(resource, cursor) VALUES (?, NULL)", (resource,)
            )
            committed_cursor = connection.execute(
                "SELECT cursor FROM checkpoints WHERE resource = ?", (resource,)
            ).fetchone()[0]
            row = connection.execute(
                "SELECT start_cursor, next_cursor, request_id, payload_sha256 "
                "FROM pending_batches WHERE resource = ?",
                (resource,),
            ).fetchone()
            pending = (start_cursor, next_cursor, request_id, digest)
            if row is None and committed_cursor != start_cursor:
                raise ValueError("batch start cursor does not match the committed checkpoint")
            if row is not None and tuple(row) != pending:
                raise ValueError("a different batch is already pending for this resource")
            connection.execute(
                "INSERT OR IGNORE INTO pending_batches "
                "(resource, start_cursor, next_cursor, request_id, payload_sha256) "
                "VALUES (?, ?, ?, ?, ?)",
                (resource, *pending),
            )

    def pending_batch(self, resource: str) -> dict[str, str | None | bool] | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT start_cursor, next_cursor, request_id, payload_sha256, conflict "
                "FROM pending_batches WHERE resource = ?",
                (resource,),
            ).fetchone()
        if row is None:
            return None
        return {
            "start_cursor": row[0],
            "next_cursor": row[1],
            "request_id": row[2],
            "payload_sha256": row[3],
            "conflict": bool(row[4]),
        }

    def mark_pending_conflict(self, resource: str, request_id: str) -> None:
        with self._connect() as connection:
            cursor = connection.execute(
                "UPDATE pending_batches SET conflict = 1 WHERE resource = ? AND request_id = ?",
                (resource, request_id),
            )
            if cursor.rowcount != 1:
                raise ValueError("matching pending batch was not found")

    def resolve_pending_by_operator(
        self, resource: str, request_id: str, *, accepted: bool
    ) -> None:
        """Resolve a changed-source ambiguity after manual CRM audit verification."""
        if not isinstance(accepted, bool):
            raise ValueError("operator acceptance decision must be boolean")
        with self._connect() as connection:
            row = connection.execute(
                "SELECT next_cursor, request_id, conflict FROM pending_batches WHERE resource = ?",
                (resource,),
            ).fetchone()
            if row is None or row[1] != request_id:
                raise ValueError("matching pending request ID is required for operator resolution")
            if not bool(row[2]):
                raise ValueError(
                    "pending batch must be marked as a conflict before operator resolution"
                )
            if accepted:
                connection.execute(
                    "UPDATE checkpoints SET cursor = ?, updated_at = CURRENT_TIMESTAMP "
                    "WHERE resource = ?",
                    (row[0], resource),
                )
            connection.execute(
                "INSERT INTO manual_resolutions(resource, request_id, resolution) VALUES (?, ?, ?)",
                (
                    resource,
                    request_id,
                    "accepted_verified" if accepted else "not_accepted_verified",
                ),
            )
            connection.execute("DELETE FROM pending_batches WHERE resource = ?", (resource,))

    def manual_resolutions(self, limit: int = 20) -> list[dict[str, str]]:
        if not 1 <= limit <= 100:
            raise ValueError("manual resolution audit limit must be between 1 and 100")
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT resource, request_id, resolution, resolved_at "
                "FROM manual_resolutions ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [
            {
                "resource": row[0],
                "request_id": row[1],
                "resolution": row[2],
                "resolved_at": row[3],
            }
            for row in rows
        ]

    def confirm_batch(self, resource: str, request_id: str, result: CrmSyncResult) -> None:
        """Advance only for the matching verified result returned by CrmClient.sync_batch."""
        if not isinstance(result, CrmSyncResult):
            raise ValueError("a verified CRM sync result is required")
        if result.request_id != request_id:
            raise ValueError("verified CRM result requestId does not match")
        if not _is_confirmed_sync_response(result.response, request_id):
            raise ValueError("verified CRM response does not confirm acceptance")
        with self._connect() as connection:
            row = connection.execute(
                "SELECT next_cursor, request_id FROM pending_batches WHERE resource = ?",
                (resource,),
            ).fetchone()
            if row is None or row[1] != request_id:
                raise ValueError("no matching pending batch")
            connection.execute(
                "UPDATE checkpoints SET cursor = ?, updated_at = CURRENT_TIMESTAMP "
                "WHERE resource = ?",
                (row[0], resource),
            )
            connection.execute("DELETE FROM pending_batches WHERE resource = ?", (resource,))

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=10)
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA foreign_keys=ON")
        return connection

    @staticmethod
    def _connect_columns(connection: sqlite3.Connection, table: str) -> list[tuple[Any, ...]]:
        return connection.execute(f"PRAGMA table_info({table})").fetchall()
