import hashlib

from alibaba_messenger.sync_models import SyncMessage, build_conversation_payload


def test_source_message_uses_crm_aliases_and_stable_fingerprint():
    message = SyncMessage.from_source(
        inquiry_id="inquiry-1", sender="buyer", content="  hello\r\nworld  ",
        raw_time="2026-09-21 10:30", sequence=2, platform_id=None,
        message_type="initial_inquiry",
    )

    assert message is not None
    assert message.model_dump(by_alias=True) == {
        "externalId": "sha256:" + hashlib.sha256(
            '["inquiry-1","inbound","2026-09-21 10:30","hello\\nworld",2]'.encode()
        ).hexdigest(),
        "direction": "inbound", "body": "hello\nworld", "translatedBody": "",
        "sentAt": "2026-09-21 10:30", "sourceTimestampRaw": "2026-09-21 10:30",
        "timestampConfidence": "high", "sourceSequence": 2, "messageType": "initialInquiry",
    }


def test_source_message_maps_seller_and_filters_system_with_timestamp_confidence():
    seller = SyncMessage.from_source(
        inquiry_id="1", sender="seller", content="reply", raw_time="2026-09-21",
        sequence=1, platform_id="platform-1", message_type="chat",
    )
    assert seller.direction == "outbound"
    assert seller.external_id == "platform-1"
    assert seller.timestamp_confidence == "medium"
    assert seller.sent_at == "2026-09-21"
    low = SyncMessage.from_source(
        inquiry_id="1", sender="buyer", content="question", raw_time="10:30",
        sequence=2, platform_id=None, message_type="chat",
    )
    assert low is not None
    assert low.timestamp_confidence == "low"
    assert low.sent_at is None
    assert SyncMessage.from_source(
        inquiry_id="1", sender="system", content="notice", raw_time="10:30",
        sequence=2, platform_id=None, message_type="chat",
    ) is None


def test_conversation_payload_fills_required_crm_fields():
    payload = build_conversation_payload({"inquiry_id": "123", "buyer_name": "", "country": ""})
    assert payload["inquiryId"] == "123"
    assert payload["buyerName"] == "Alibaba Buyer 123"
    assert payload["country"] == ""
    assert payload["createdAtRaw"] == ""
    assert payload["updatedAtRaw"] == ""
