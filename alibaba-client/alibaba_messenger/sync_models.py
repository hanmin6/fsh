"""Pure CRM sync contract normalization; no browser, HTTP, or disk access."""
from __future__ import annotations

import hashlib
import json
import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class SyncMessage(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    external_id: str = Field(alias="externalId")
    direction: Literal["inbound", "outbound"]
    body: str
    translated_body: str = Field(default="", alias="translatedBody")
    sent_at: str | None = Field(default=None, alias="sentAt")
    source_timestamp_raw: str = Field(alias="sourceTimestampRaw")
    timestamp_confidence: Literal["high", "medium", "low"] = Field(alias="timestampConfidence")
    source_sequence: int = Field(alias="sourceSequence", ge=1)
    message_type: Literal["initialInquiry", "chat"] = Field(alias="messageType")

    @classmethod
    def from_source(
        cls, inquiry_id: str, sender: str, content: str, raw_time: str,
        sequence: int, platform_id: str | None, message_type: str = "chat",
        translation: str = "",
    ) -> "SyncMessage | None":
        sender = (sender or "").strip().lower()
        if sender == "system":
            return None
        direction = "outbound" if sender == "seller" else "inbound"
        body = (content or "").replace("\r\n", "\n").replace("\r", "\n").strip()
        translated = (translation or "").replace("\r\n", "\n").replace("\r", "\n").strip()
        raw = (raw_time or "").strip()
        fingerprint = json.dumps([str(inquiry_id), direction, raw, body, int(sequence)], ensure_ascii=False, separators=(",", ":"))
        if re.search(r"\d{4}[-/.]\d{1,2}[-/.]\d{1,2}\s+\d{1,2}:\d{1,2}", raw):
            confidence = "high"
        elif re.fullmatch(r"\d{4}[-/.]\d{1,2}[-/.]\d{1,2}", raw):
            confidence = "medium"
        else:
            confidence = "low"
        sent_at = raw if confidence in {"high", "medium"} else None
        return cls(
            externalId=(platform_id or "sha256:" + hashlib.sha256(fingerprint.encode("utf-8")).hexdigest()),
            direction=direction, body=body, translatedBody=translated, sentAt=sent_at,
            sourceTimestampRaw=raw, timestampConfidence=confidence, sourceSequence=sequence,
            messageType="initialInquiry" if message_type in {"initial_inquiry", "initialInquiry"} else "chat",
        )


def build_conversation_payload(conversation: dict) -> dict:
    inquiry_id = str(conversation["inquiry_id"])
    return {
        "inquiryId": inquiry_id,
        "buyerExternalId": conversation.get("buyer_external_id"),
        "buyerName": (conversation.get("buyer_name") or "").strip() or f"Alibaba Buyer {inquiry_id}",
        "country": conversation.get("country") or "",
        "subject": conversation.get("subject") or "",
        "sourceStatus": conversation.get("status") or "",
        "unreadCount": int(conversation.get("unread_count") or 0),
        "createdAtRaw": conversation.get("create_time") or "",
        "updatedAtRaw": conversation.get("last_time") or "",
    }
