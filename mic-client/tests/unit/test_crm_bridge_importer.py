from __future__ import annotations

from typing import Any

import pytest

from mic_gateway.crm_bridge.importer import ImporterError, IncompleteHistoryError, MicCrmImporter
from mic_gateway.crm_bridge.state import CrmBridgeState


class FakeGateway:
    def __init__(
        self, conversations: list[dict[str, Any]], messages: dict[str, list[dict[str, Any]]]
    ):
        self.conversations = conversations
        self.messages = messages
        self.conversation_calls: list[str | None] = []
        self.message_calls: list[tuple[str, str | None]] = []

    def list_conversations(
        self, limit: int = 200, cursor: str | None = None, updated_after: str | None = None
    ) -> dict[str, Any]:
        self.conversation_calls.append(cursor)
        offset = int(cursor or 0)
        page = self.conversations[offset : offset + 1]
        next_cursor = str(offset + 1) if offset + 1 < len(self.conversations) else None
        return {"items": page, "next_cursor": next_cursor}

    def list_messages(
        self, conversation_id: str, limit: int = 200, cursor: str | None = None
    ) -> dict[str, Any]:
        self.message_calls.append((conversation_id, cursor))
        offset = int(cursor or 0)
        page = self.messages[conversation_id][offset : offset + 1]
        next_cursor = str(offset + 1) if offset + 1 < len(self.messages[conversation_id]) else None
        return {"items": page, "next_cursor": next_cursor}


class FakeCrm:
    def __init__(self, *, fail_first: bool = False):
        self.payloads: list[dict[str, Any]] = []
        self.fail_first = fail_first

    def sync_batch(self, payload: dict[str, Any], request_id: str) -> Any:
        self.payloads.append(payload)
        if self.fail_first:
            self.fail_first = False
            raise RuntimeError("simulated interrupted request")
        return _verified(request_id)


def _verified(request_id: str) -> Any:
    from mic_gateway.crm_bridge.crm_client import CrmClient

    return CrmClient(
        "http://localhost",
        "agent",
        "token",
        opener=lambda request, timeout: _Response({"requestId": request_id, "accepted": True}),
    ).sync_batch({}, request_id)


class _Response:
    status = 200

    def __init__(self, payload: dict[str, Any]):
        import json

        self.body = json.dumps(payload).encode()

    def read(self) -> bytes:
        return self.body


def _conversation(*, complete: bool = True) -> dict[str, Any]:
    return {
        "id": "gateway-conversation-1",
        "source_id": "mic-source-1",
        "buyer_reference": "buyer-9",
        "inquiry_subject": "Need a quote",
        "unread": True,
        "history_complete": complete,
    }


def _message(source_id: str, sequence: int, direction: str, content: str) -> dict[str, Any]:
    return {
        "id": f"gateway-{source_id}",
        "source_id": source_id,
        "source_sequence": sequence,
        "direction": direction,
        "sender_label": "buyer" if direction == "inbound" else "seller",
        "content": content,
        "source_timestamp_raw": f"2026-01-01T00:00:0{sequence}Z",
        "source_timestamp_confidence": "high",
        "attachment_metadata": [],
    }


def test_backfill_paginates_conversations_and_complete_bilateral_history(tmp_path: Any) -> None:
    gateway = FakeGateway(
        [
            _conversation(),
            {
                **_conversation(),
                "id": "gateway-conversation-2",
                "source_id": "mic-source-2",
                "buyer_reference": "buyer-10",
            },
        ],
        {
            "gateway-conversation-1": [
                _message("msg-1", 1, "inbound", "initial inquiry"),
                _message("msg-2", 2, "outbound", "seller reply"),
                _message("msg-3", 3, "inbound", "buyer follow-up"),
            ],
            "gateway-conversation-2": [_message("msg-4", 1, "inbound", "second buyer")],
        },
    )
    crm = FakeCrm()
    state = CrmBridgeState(tmp_path)

    result = MicCrmImporter(gateway, crm, state, account_handle="mic-account").backfill()

    assert result.conversations == 2
    assert result.messages == 4
    assert gateway.conversation_calls == [None, "1"]
    assert [payload["accountHandle"] for payload in crm.payloads] == ["mic-account", "mic-account"]
    first = crm.payloads[0]
    assert first["conversation"]["sourceId"] == "mic-source-1"
    assert first["conversation"]["buyerName"] == "MIC 买家 buyer-9"
    assert first["conversation"]["buyerNameIsPlaceholder"] is True
    assert first["conversation"]["unreadCount"] == 1
    assert [message["externalId"] for message in first["messages"]] == ["msg-1", "msg-2", "msg-3"]
    assert [message["direction"] for message in first["messages"]] == [
        "inbound",
        "outbound",
        "inbound",
    ]
    assert first["messages"][0]["messageType"] == "initialInquiry"
    assert first["messages"][0]["sourceSequence"] == 1
    assert first["messages"][0]["sourceTimestampRaw"].endswith("Z")


def test_backfill_propagates_real_buyer_name_and_country(tmp_path: Any) -> None:
    gateway = FakeGateway(
        [
            {
                **_conversation(),
                "buyer_name": "Acme Buyer Corp",
                "country": "Germany",
            },
        ],
        {
            "gateway-conversation-1": [
                _message("msg-1", 1, "inbound", "initial inquiry"),
            ],
        },
    )
    crm = FakeCrm()
    state = CrmBridgeState(tmp_path)

    result = MicCrmImporter(gateway, crm, state, account_handle="mic-account").backfill()

    assert result.conversations == 1
    first = crm.payloads[0]
    assert first["conversation"]["buyerName"] == "Acme Buyer Corp"
    assert first["conversation"]["buyerNameIsPlaceholder"] is False
    assert first["conversation"]["country"] == "Germany"


def test_incomplete_history_is_refused_without_crm_write(tmp_path: Any) -> None:
    gateway = FakeGateway([_conversation(complete=False)], {"gateway-conversation-1": []})
    crm = FakeCrm()

    with pytest.raises(IncompleteHistoryError, match="history_complete"):
        MicCrmImporter(gateway, crm, CrmBridgeState(tmp_path), account_handle="account").backfill()

    assert crm.payloads == []


def test_interrupted_crm_page_reuses_stable_request_and_checkpoint(tmp_path: Any) -> None:
    gateway = FakeGateway(
        [_conversation()], {"gateway-conversation-1": [_message("msg-1", 1, "inbound", "hello")]}
    )
    crm = FakeCrm(fail_first=True)
    state = CrmBridgeState(tmp_path)
    importer = MicCrmImporter(gateway, crm, state, account_handle="account")

    with pytest.raises(RuntimeError, match="interrupted"):
        importer.backfill()
    assert state.checkpoint("conversations") is None

    importer.backfill()

    assert crm.payloads[0] == crm.payloads[1]
    assert crm.payloads[0]["requestId"] == crm.payloads[1]["requestId"]
    assert state.checkpoint("conversations") == "__mic_import_complete__"


def test_batches_never_exceed_one_hundred_messages(tmp_path: Any) -> None:
    messages = [_message(f"msg-{i}", i, "inbound", f"body {i}") for i in range(1, 202)]
    gateway = FakeGateway([_conversation()], {"gateway-conversation-1": messages})
    crm = FakeCrm()

    MicCrmImporter(gateway, crm, CrmBridgeState(tmp_path), account_handle="account").backfill()

    assert [len(payload["messages"]) for payload in crm.payloads] == [100, 100, 1]
    assert [payload["batchNo"] for payload in crm.payloads] == [1, 2, 3]
    assert len({payload["jobId"] for payload in crm.payloads}) == 1
    assert len({payload["requestId"] for payload in crm.payloads}) == 3


def test_once_rereads_history_for_new_source_updates(tmp_path: Any) -> None:
    old = _message("msg-1", 1, "inbound", "hello")
    gateway = FakeGateway([_conversation()], {"gateway-conversation-1": [old]})
    crm = FakeCrm()
    importer = MicCrmImporter(gateway, crm, CrmBridgeState(tmp_path), account_handle="account")

    importer.once()
    gateway.messages["gateway-conversation-1"].append(
        _message("msg-2", 2, "outbound", "updated reply")
    )
    importer.once()

    assert len(gateway.conversation_calls) == 2
    assert len(crm.payloads) == 2
    assert [message["externalId"] for message in crm.payloads[-1]["messages"]] == ["msg-1", "msg-2"]
    assert crm.payloads[0]["requestId"] != crm.payloads[1]["requestId"]


def test_once_uses_crm_incremental_mode(tmp_path: Any) -> None:
    gateway = FakeGateway(
        [_conversation()], {"gateway-conversation-1": [_message("msg-1", 1, "inbound", "hello")]}
    )
    crm = FakeCrm()

    MicCrmImporter(gateway, crm, CrmBridgeState(tmp_path), account_handle="account").once()

    assert crm.payloads[0]["syncMode"] == "incremental"


def test_message_sender_and_sanitized_attachment_metadata_are_preserved(tmp_path: Any) -> None:
    first = _message("msg-1", 1, "inbound", "hello")
    first["attachment_metadata"] = [
        {
            "name": "spec-sheet.pdf",
            "mediaType": "application/pdf",
            "size": 2048,
            "url": "https://invalid.example/download?token=synthetic-secret",
            "extra": "discard-this",
        },
        {"name": "missing-values.pdf"},
        {"url": "https://invalid.example/private"},
    ]
    gateway = FakeGateway([_conversation()], {"gateway-conversation-1": [first]})
    crm = FakeCrm()

    MicCrmImporter(gateway, crm, CrmBridgeState(tmp_path), account_handle="account").backfill()

    message = crm.payloads[0]["messages"][0]
    assert message["senderName"] == "buyer"
    assert message["attachmentMetadata"] == {
        "items": [
            {"name": "spec-sheet.pdf", "mediaType": "application/pdf", "size": 2048},
            {"name": "missing-values.pdf", "mediaType": None, "size": None},
        ]
    }
    assert "invalid.example" not in repr(message)
    assert "synthetic-secret" not in repr(message)
    assert "discard-this" not in repr(message)


def test_long_external_ids_get_stable_hash_aliases_and_subject_is_bounded(tmp_path: Any) -> None:
    conversation = _conversation()
    conversation["source_id"] = "conversation-" + "c" * 240
    conversation["inquiry_subject"] = "S" * 400
    messages = [
        _message("M" * 240 + "A", 1, "inbound", "first"),
        _message("M" * 240 + "B", 2, "outbound", "second"),
    ]
    gateway = FakeGateway([conversation], {"gateway-conversation-1": messages})
    crm = FakeCrm()
    importer = MicCrmImporter(gateway, crm, CrmBridgeState(tmp_path), account_handle="account")

    importer.once()
    importer.once()

    first = crm.payloads[0]
    replay = crm.payloads[1]
    conversation_id = first["conversation"]["sourceId"]
    message_ids = [message["externalId"] for message in first["messages"]]
    assert len(conversation_id) <= 191
    assert conversation_id != conversation["source_id"]
    assert len(set(message_ids)) == 2
    assert all(len(message_id) <= 191 for message_id in message_ids)
    assert conversation["source_id"] not in repr(first)
    assert all(source_message["source_id"] not in repr(first) for source_message in messages)
    assert message_ids == [message["externalId"] for message in replay["messages"]]
    assert conversation_id == replay["conversation"]["sourceId"]
    assert len(first["conversation"]["subject"]) == 255

    other_crm = FakeCrm()
    MicCrmImporter(
        gateway,
        other_crm,
        CrmBridgeState(tmp_path / "other-account"),
        account_handle="other-account",
    ).once()
    assert other_crm.payloads[0]["conversation"]["sourceId"] != conversation_id


def test_changed_source_after_ambiguous_response_marks_recoverable_conflict(tmp_path: Any) -> None:
    messages = [_message("msg-1", 1, "inbound", "before")]
    gateway = FakeGateway([_conversation()], {"gateway-conversation-1": messages})
    crm = FakeCrm(fail_first=True)
    state = CrmBridgeState(tmp_path)
    importer = MicCrmImporter(gateway, crm, state, account_handle="account")

    with pytest.raises(RuntimeError, match="interrupted"):
        importer.once()
    pending_before = state.pending_batch("conversations:once")
    assert pending_before is not None

    # A pre-upgrade journal has no retained original body and still needs an audit.
    for spool in state.replay_directory.glob("*.json"):
        spool.unlink()

    messages[0]["content"] = "after"
    with pytest.raises(ImporterError, match="pending_batch_conflict"):
        importer.once()

    pending_after = state.pending_batch("conversations:once")
    assert pending_after is not None
    assert pending_after["request_id"] == pending_before["request_id"]
    assert pending_after["conflict"] is True
    assert state.checkpoint("conversations:once") is None
    assert len(crm.payloads) == 1


def test_changed_source_replays_retained_original_before_new_messages(tmp_path: Any) -> None:
    messages = [_message("msg-1", 1, "inbound", "before")]
    gateway = FakeGateway([_conversation()], {"gateway-conversation-1": messages})
    crm = FakeCrm(fail_first=True)
    state = CrmBridgeState(tmp_path)
    importer = MicCrmImporter(gateway, crm, state, account_handle="account")
    with pytest.raises(RuntimeError, match="interrupted"):
        importer.once()
    messages.append(_message("msg-2", 2, "inbound", "new message"))
    importer.once()
    assert crm.payloads[0] == crm.payloads[1]
    assert len(crm.payloads[1]["messages"]) == 1
    assert len(crm.payloads[2]["messages"]) == 2
    assert state.pending_batch("conversations:once") is None
    assert list(state.replay_directory.glob("*.json")) == []


def test_unrepresentable_conversation_id_skips_only_that_conversation(tmp_path: Any) -> None:
    bad = {**_conversation(), "source_id": "\ud800"}
    later = {
        **_conversation(),
        "id": "gateway-conversation-2",
        "source_id": "later-source",
        "buyer_reference": "buyer-10",
    }
    gateway = FakeGateway(
        [bad, later],
        {"gateway-conversation-1": [], "gateway-conversation-2": []},
    )
    crm = FakeCrm()
    state = CrmBridgeState(tmp_path)

    result = MicCrmImporter(gateway, crm, state, account_handle="account").once()

    assert result.conversations == 1
    assert result.action_required_codes == ["source_identity_alias_unavailable"]
    assert [payload["conversation"]["sourceId"] for payload in crm.payloads] == ["later-source"]
    assert state.checkpoint("conversations:once") is None
