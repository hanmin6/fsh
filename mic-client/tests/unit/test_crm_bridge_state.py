from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from mic_gateway.crm_bridge.crm_client import CrmClient, CrmPermanentError, CrmSyncResult
from mic_gateway.crm_bridge.state import CrmBridgeState


def test_checkpoint_advances_only_after_confirmed_matching_response(tmp_path: Path) -> None:
    state = CrmBridgeState(tmp_path)
    payload = {"messages": [{"body": "synthetic buyer text"}]}
    state.stage_batch(
        "backfill",
        start_cursor=None,
        next_cursor="cursor-page-2",
        request_id="stable-job:1",
        payload=payload,
    )

    assert state.checkpoint("backfill") is None
    pending = state.pending_batch("backfill")
    assert pending is not None
    assert pending["start_cursor"] is None
    assert pending["next_cursor"] == "cursor-page-2"
    assert pending["request_id"] == "stable-job:1"
    assert len(pending["payload_sha256"] or "") == 64
    with pytest.raises(ValueError, match="requestId does not match"):
        state.confirm_batch("backfill", "different-id", _verified_success("stable-job:1"))
    assert state.checkpoint("backfill") is None

    confirmed = _verified_success("stable-job:1")
    state.confirm_batch("backfill", "stable-job:1", confirmed)
    assert state.checkpoint("backfill") == "cursor-page-2"
    assert state.pending_batch("backfill") is None
    with pytest.raises(ValueError, match="does not match"):
        state.stage_batch(
            "backfill",
            start_cursor="stale-cursor",
            next_cursor="cursor-page-3",
            request_id="stable-job:2",
            payload={"messages": []},
        )


def test_pending_batch_survives_restart_and_reuses_request_id(tmp_path: Path) -> None:
    payload = {"request": "synthetic"}
    first = CrmBridgeState(tmp_path)
    first.stage_batch(
        "messages:conversation-1",
        start_cursor=None,
        next_cursor="page-1",
        request_id="job-1:conversation-1:1",
        payload={"request": "synthetic-page-one"},
    )
    first.confirm_batch(
        "messages:conversation-1",
        "job-1:conversation-1:1",
        _verified_success("job-1:conversation-1:1"),
    )
    first.stage_batch(
        "messages:conversation-1",
        start_cursor="page-1",
        next_cursor="page-2",
        request_id="job-1:conversation-1:2",
        payload=payload,
    )

    restarted = CrmBridgeState(tmp_path)
    pending = restarted.pending_batch("messages:conversation-1")
    assert pending is not None
    assert pending["request_id"] == "job-1:conversation-1:2"
    assert pending["start_cursor"] == "page-1"
    assert pending["next_cursor"] == "page-2"
    with pytest.raises(ValueError, match="different batch"):
        restarted.stage_batch(
            "messages:conversation-1",
            start_cursor="page-1",
            next_cursor="page-3",
            request_id="new-id",
            payload=payload,
        )


def test_state_persists_only_digest_and_cursor_metadata(tmp_path: Path) -> None:
    buyer_text = "synthetic buyer message that must not be stored"
    state = CrmBridgeState(tmp_path)
    state.stage_batch(
        "inquiries",
        start_cursor=None,
        next_cursor=None,
        request_id="job-1:batch-1",
        payload={"body": buyer_text},
    )

    connection = sqlite3.connect(state.path)
    stored = " ".join(
        str(cell) for row in connection.execute("SELECT * FROM pending_batches") for cell in row
    )
    connection.close()
    assert buyer_text not in stored
    assert "token" not in stored.lower()


@pytest.mark.parametrize(
    "response",
    [
        {},
        {"requestId": "stable-job:1", "success": False, "error": "rejected"},
        {"requestId": "different-request", "accepted": True},
    ],
)
def test_unverified_or_mismatched_response_does_not_advance_checkpoint(
    tmp_path: Path, response: dict[str, object]
) -> None:
    state = CrmBridgeState(tmp_path)
    state.stage_batch(
        "backfill",
        start_cursor=None,
        next_cursor="cursor-page-2",
        request_id="stable-job:1",
        payload={"messages": []},
    )

    with pytest.raises(ValueError):
        state.confirm_batch("backfill", "stable-job:1", response)  # type: ignore[arg-type]

    assert state.checkpoint("backfill") is None
    assert state.pending_batch("backfill") is not None


def test_forged_failure_result_cannot_advance_checkpoint(tmp_path: Path) -> None:
    state = CrmBridgeState(tmp_path)
    state.stage_batch(
        "backfill",
        start_cursor=None,
        next_cursor="cursor-page-2",
        request_id="stable-job:1",
        payload={"messages": []},
    )
    genuine = _verified_success("stable-job:1")
    forged = CrmSyncResult(
        "stable-job:1",
        {"requestId": "stable-job:1", "accepted": True, "error": "rejected"},
        _verification=genuine._verification,
    )

    with pytest.raises(ValueError, match="does not confirm acceptance"):
        state.confirm_batch("backfill", "stable-job:1", forged)

    assert state.checkpoint("backfill") is None
    assert state.pending_batch("backfill") is not None


def test_client_marks_only_matching_successful_sync_response_verified() -> None:
    client = CrmClient(
        "http://localhost:8080",
        "mic-agent",
        "synthetic-token",
        opener=lambda request, timeout: _Response(
            200, {"requestId": "stable-job:1", "accepted": True}
        ),
    )

    result = client.sync_batch({"jobId": "stable-job"}, "stable-job:1")

    assert type(result).__name__ == "CrmSyncResult"
    assert result.request_id == "stable-job:1"
    assert result.response["accepted"] is True


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"requestId": "stable-job:1"},
        {"error": "rejected"},
        {"requestId": "stable-job:1", "error": "rejected"},
        {"requestId": "stable-job:1", "success": False},
        {"requestId": "stable-job:1", "accepted": True, "error": "rejected"},
        {"requestId": "another-request", "accepted": True},
        {"requestId": "stable-job:1", "accepted": False},
    ],
)
def test_client_rejects_unconfirmed_sync_response(body: dict[str, object]) -> None:
    client = CrmClient(
        "http://localhost:8080",
        "mic-agent",
        "synthetic-token",
        opener=lambda request, timeout: _Response(200, body),
    )

    with pytest.raises(CrmPermanentError):
        client.sync_batch({"jobId": "stable-job"}, "stable-job:1")


class _Response:
    def __init__(self, status: int, payload: dict[str, object]) -> None:
        import json

        self.status = status
        self.body = json.dumps(payload).encode()

    def read(self) -> bytes:
        return self.body


def _verified_success(request_id: str) -> CrmSyncResult:
    client = CrmClient(
        "http://localhost:8080",
        "mic-agent",
        "synthetic-token",
        opener=lambda request, timeout: _Response(200, {"requestId": request_id, "accepted": True}),
    )
    return client.sync_batch({"jobId": "stable-job"}, request_id)


def test_pending_conflict_can_be_resolved_only_with_explicit_operator_decision(
    tmp_path: Path,
) -> None:
    state = CrmBridgeState(tmp_path)
    state.stage_batch(
        "conversations:once",
        start_cursor=None,
        next_cursor="next",
        request_id="stable-request",
        payload={"safe": True},
    )

    state.mark_pending_conflict("conversations:once", "stable-request")
    pending = state.pending_batch("conversations:once")

    assert pending is not None
    assert pending["conflict"] is True
    assert state.checkpoint("conversations:once") is None
    with pytest.raises(ValueError, match="operator"):
        state.resolve_pending_by_operator("conversations:once", "wrong-request", accepted=True)

    state.resolve_pending_by_operator("conversations:once", "stable-request", accepted=False)

    assert state.pending_batch("conversations:once") is None
    assert state.checkpoint("conversations:once") is None


def test_existing_pending_batch_schema_migrates_conflict_flag(tmp_path: Path) -> None:
    state = CrmBridgeState(tmp_path)
    connection = sqlite3.connect(state.path)
    connection.execute("DROP TABLE pending_batches")
    connection.execute(
        "CREATE TABLE pending_batches ("
        "resource TEXT PRIMARY KEY, start_cursor TEXT, next_cursor TEXT, "
        "request_id TEXT NOT NULL, payload_sha256 TEXT NOT NULL)"
    )
    connection.execute("INSERT INTO checkpoints(resource, cursor) VALUES ('legacy', NULL)")
    connection.execute(
        "INSERT INTO pending_batches(resource, start_cursor, next_cursor, request_id,"
        "payload_sha256) "
        "VALUES ('legacy', NULL, 'next', 'legacy-request', 'digest')"
    )
    connection.commit()
    connection.close()

    migrated = CrmBridgeState(tmp_path)

    pending = migrated.pending_batch("legacy")
    assert pending is not None
    assert pending["conflict"] is False


def test_operator_resolution_writes_nonsecret_audit_record(tmp_path: Path) -> None:
    state = CrmBridgeState(tmp_path)
    state.stage_batch(
        "conversations:once",
        start_cursor=None,
        next_cursor="next",
        request_id="audited-request-id",
        payload={"body": "private buyer content"},
    )
    state.mark_pending_conflict("conversations:once", "audited-request-id")

    state.resolve_pending_by_operator("conversations:once", "audited-request-id", accepted=False)

    audit = state.manual_resolutions()
    assert len(audit) == 1
    assert audit[0]["request_id"] == "audited-request-id"
    assert audit[0]["resolution"] == "not_accepted_verified"
    assert "private buyer content" not in repr(audit)
