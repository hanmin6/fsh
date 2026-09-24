"""Cross-system MIC importer acceptance test against an isolated EspoCRM stack.

Runtime execution requires a local test stack and test-only credentials:

    $env:ESPOCRM_API_URL = 'http://127.0.0.1:18082/api/v1'
    $env:ESPOCRM_ADMIN_USERNAME = 'admin'
    $env:ESPOCRM_ADMIN_PASSWORD = '<isolated test admin password>'
    $env:FUSANHE_AUTOMATION_TOKEN = '<isolated test bootstrap token>'
    $env:RUN_MIC_BRIDGE_RUNTIME = '1'
    uv run pytest tests/integration/test_crm_bridge_runtime.py -v

The default run skips this test. Runtime data uses fictional, per-run IDs. The
test only calls read and sync endpoints; it never queues or sends a message.
"""

from __future__ import annotations

import base64
import json
import os
import urllib.error
import urllib.parse
import urllib.request
import uuid
from collections.abc import Mapping
from typing import Any

import pytest

from mic_gateway.crm_bridge.crm_client import CrmClient, CrmSyncResult
from mic_gateway.crm_bridge.importer import MicCrmImporter
from mic_gateway.crm_bridge.state import CrmBridgeState

BASE = os.getenv("ESPOCRM_API_URL", "http://127.0.0.1:18082/api/v1").rstrip("/")
ADMIN_USER = os.getenv("ESPOCRM_ADMIN_USERNAME", "admin")
ADMIN_PASS = os.getenv("ESPOCRM_ADMIN_PASSWORD", "phase1-test-admin-password")
BOOTSTRAP_TOKEN = os.getenv(
    "FUSANHE_AUTOMATION_TOKEN", "phase1-test-automation-token-0123456789abcdef"
)
LOOPBACK_HOSTS = {"localhost", "127.0.0.1", "::1"}


def _assert_loopback_base_url() -> None:
    try:
        parsed = urllib.parse.urlparse(BASE)
        port = parsed.port
    except ValueError as error:
        raise RuntimeError("ESPOCRM_API_URL is invalid") from error
    if parsed.scheme not in {"http", "https"} or parsed.hostname not in LOOPBACK_HOSTS:
        raise RuntimeError("refusing MIC bridge runtime tests against a non-loopback CRM URL")
    if port != 18082:
        raise RuntimeError("refusing MIC bridge runtime tests unless CRM is on test port 18082")


def _send(
    request: urllib.request.Request, *, expect_error: bool = False
) -> tuple[int, dict[str, Any]]:
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            raw = response.read()
            value = json.loads(raw) if raw else {}
            return response.status, value if isinstance(value, dict) else {}
    except urllib.error.HTTPError as error:
        raw = error.read()
        try:
            value = json.loads(raw) if raw else {}
        except (json.JSONDecodeError, UnicodeDecodeError):
            value = {}
        if not expect_error:
            raise AssertionError(
                f"CRM returned HTTP {error.code} for {request.full_url}"
            ) from error
        return error.code, value if isinstance(value, dict) else {}


def _api(
    path: str,
    *,
    method: str = "GET",
    body: Mapping[str, Any] | None = None,
    headers: Mapping[str, str] | None = None,
    admin: bool = False,
) -> dict[str, Any]:
    request_headers = {"Content-Type": "application/json"}
    if admin:
        encoded = base64.b64encode(f"{ADMIN_USER}:{ADMIN_PASS}".encode()).decode()
        request_headers["Authorization"] = "Basic " + encoded
    if headers:
        request_headers.update(headers)
    encoded_body = None if body is None else json.dumps(body).encode("utf-8")
    request = urllib.request.Request(
        BASE + path, encoded_body, request_headers, method=method
    )
    _, value = _send(request)
    return value


def _list(entity: str, where: list[dict[str, str]]) -> dict[str, Any]:
    search_params = urllib.parse.urlencode(
        {
            "searchParams": json.dumps(
                {"maxSize": 100, "where": where}, separators=(",", ":")
            )
        }
    )
    return _api(f"/{entity}?{search_params}", admin=True)


class _SyntheticMicReadClient:
    """Stable, paginated fixture data with no access to a real MIC account."""

    def __init__(self, stamp: str) -> None:
        self.buyer_reference = f"fixture-buyer-{stamp[:18]}"
        self.conversations = [
            {
                "id": f"gateway-{stamp[:16]}-{number}",
                "source_id": f"mic-source-{stamp[:16]}-{number}",
                "buyer_reference": self.buyer_reference,
                "inquiry_subject": f"Synthetic MIC inquiry {number}",
                "country": "Fixtureland",
                "unread": True,
                "history_complete": True,
            }
            for number in (1, 2)
        ]
        self.messages = {
            conversation["id"]: [
                {
                    "id": f"mic-message-{stamp[:16]}-{number}-inquiry",
                    "source_sequence": 1,
                    "direction": "inbound",
                    "message_type": "initialInquiry",
                    "sender_label": "Synthetic MIC Buyer",
                    "content": f"Synthetic inquiry body {number}",
                    "source_timestamp_raw": "2026-09-24T01:00:00Z",
                    "source_timestamp_confidence": "high",
                    "attachment_metadata": [
                        {
                            "name": f"fixture-catalog-{number}.pdf",
                            "mediaType": "application/pdf",
                            "size": 2048,
                        }
                    ],
                },
                {
                    "id": f"mic-message-{stamp[:16]}-{number}-reply",
                    "source_sequence": 2,
                    "direction": "outbound",
                    "message_type": "chat",
                    "sender_label": "Synthetic MIC Seller",
                    "content": f"Synthetic seller reply {number}",
                    "source_timestamp_raw": "2026-09-24T01:01:00Z",
                    "source_timestamp_confidence": "high",
                    "attachment_metadata": [],
                },
            ]
            for number, conversation in enumerate(self.conversations, start=1)
        }

    def list_conversations(
        self, limit: int = 200, cursor: str | None = None
    ) -> dict[str, Any]:
        del limit
        offset = int(cursor or 0)
        items = self.conversations[offset : offset + 1]
        next_cursor = str(offset + 1) if offset + 1 < len(self.conversations) else None
        return {"items": items, "next_cursor": next_cursor}

    def list_messages(
        self, conversation_id: str, limit: int = 200, cursor: str | None = None
    ) -> dict[str, Any]:
        del limit
        rows = self.messages[conversation_id]
        offset = int(cursor or 0)
        items = rows[offset : offset + 1]
        next_cursor = str(offset + 1) if offset + 1 < len(rows) else None
        return {"items": items, "next_cursor": next_cursor}


class _RecordingCrmClient:
    """Capture accepted responses while forwarding through the real CRM client."""

    def __init__(self, client: CrmClient) -> None:
        self.client = client
        self.results: list[CrmSyncResult] = []

    def sync_batch(self, payload: Mapping[str, Any], request_id: str) -> CrmSyncResult:
        result = self.client.sync_batch(payload, request_id)
        self.results.append(result)
        return result


def test_synthetic_mic_backfill_once_and_replay_against_isolated_crm(tmp_path: Any) -> None:
    _assert_loopback_base_url()
    if os.getenv("RUN_MIC_BRIDGE_RUNTIME") != "1":
        pytest.skip("set RUN_MIC_BRIDGE_RUNTIME=1 to execute isolated MIC bridge runtime test")

    stamp = uuid.uuid4().hex
    status = _api("/Fusanhe/status", admin=True)
    assert status.get("outboundPaused") is True
    admin = _api("/App/user", admin=True)
    assert admin.get("user", {}).get("id")

    agent_key = f"mic-bridge-test-{stamp[:20]}"
    bootstrap_client = CrmClient(BASE, agent_key, max_retries=0)
    agent_token = bootstrap_client.register(BOOTSTRAP_TOKEN)
    crm = _RecordingCrmClient(CrmClient(BASE, agent_key, agent_token, max_retries=0))
    gateway = _SyntheticMicReadClient(stamp)
    account_handle = f"fixture-mic-{stamp[:18]}"
    importer = MicCrmImporter(
        gateway, crm, CrmBridgeState(tmp_path), account_handle=account_handle
    )

    backfill = importer.backfill()
    once = importer.once()
    replay = importer.once()

    assert (backfill.conversations, backfill.messages) == (2, 4)
    assert (once.conversations, once.messages) == (2, 4)
    assert (replay.conversations, replay.messages) == (2, 4)
    assert len(crm.results) == 6
    responses = [dict(result.response) for result in crm.results]
    assert all(response.get("accepted") is True for response in responses)
    assert sum(int(response.get("createdMessages", 0)) for response in responses[:2]) == 4
    assert sum(int(response.get("createdMessages", 0)) for response in responses[2:]) == 0
    assert all(
        int(response.get("deduplicatedMessages", 0)) == 2 for response in responses[2:]
    )

    source_ids = [conversation["source_id"] for conversation in gateway.conversations]
    channels = _list(
        "ExternalChannel",
        [
            {"type": "equals", "attribute": "type", "value": "MadeInChina"},
            {"type": "equals", "attribute": "accountHandle", "value": account_handle},
        ],
    )
    assert channels["total"] == 1
    channel_id = channels["list"][0]["id"]
    conversations = [
        _list(
            "ExternalConversation",
            [{"type": "equals", "attribute": "externalId", "value": source_id}],
        )
        for source_id in source_ids
    ]
    assert [rows["total"] for rows in conversations] == [1, 1]
    conversation_rows = [rows["list"][0] for rows in conversations]
    lead_ids = {row.get("leadId") for row in conversation_rows}
    assert len(lead_ids) == 1
    lead_id = next(iter(lead_ids))
    assert lead_id
    lead = _api(f"/Lead/{urllib.parse.quote(str(lead_id), safe='')}", admin=True)
    assert lead.get("id") == lead_id
    assert lead.get("name") == f"MIC 买家 {gateway.buyer_reference}"
    matching_leads = _list(
        "Lead",
        [{"type": "equals", "attribute": "name", "value": lead["name"]}],
    )
    assert matching_leads["total"] == 1

    for conversation, conversation_fixture in zip(
        conversation_rows, gateway.conversations, strict=True
    ):
        assert conversation.get("channelId") == channel_id
        assert conversation.get("externalUserId") == gateway.buyer_reference
        assert conversation.get("backfillCompletedAt")
        assert conversation.get("unreadCount") == 0
        where = [
            {
                "type": "equals",
                "attribute": "conversationId",
                "value": conversation["id"],
            }
        ]
        messages = _list("ExternalMessage", where)
        assert messages["total"] == 2
        rows_by_direction = {row["direction"]: row for row in messages["list"]}
        assert set(rows_by_direction) == {"inbound", "outbound"}
        inquiry = rows_by_direction["inbound"]
        assert inquiry.get("senderName") == "Synthetic MIC Buyer"
        assert inquiry.get("attachmentMetadata") == {
            "items": [
                {
                    "name": f"fixture-catalog-{conversation_fixture['source_id'][-1]}.pdf",
                    "mediaType": "application/pdf",
                    "size": 2048,
                }
            ]
        }
        assert rows_by_direction["outbound"].get("senderName") == "Synthetic MIC Seller"
        assert _list("AIReplyDraft", where)["total"] == 0
        assert _list("OutboundTask", where)["total"] == 0
