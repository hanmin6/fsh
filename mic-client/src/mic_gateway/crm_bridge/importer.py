from __future__ import annotations

import hashlib
import json
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from collections.abc import Callable, Mapping
from typing import Any, Protocol

from mic_gateway.crm_bridge.config import CrmBridgeConfig
from mic_gateway.crm_bridge.crm_client import CrmClient, CrmSyncResult
from mic_gateway.crm_bridge.state import CrmBridgeState

_COMPLETE_CURSOR = "__mic_import_complete__"


class ImporterError(RuntimeError):
    """MIC data could not be imported safely."""


class PendingBatchConflictError(ImporterError):
    """A pending CRM request cannot safely be replayed from the current source snapshot."""

    def __init__(self, resource: str, request_id: str) -> None:
        self.resource = resource
        self.request_id = request_id
        super().__init__("pending_batch_conflict")


class SourceIdentityAliasError(ImporterError):
    """A long source ID could not be represented without identity ambiguity."""

    def __init__(self) -> None:
        super().__init__("source_identity_alias_unavailable")


class ReadGateway(Protocol):
    def list_conversations(self, limit: int = 200, cursor: str | None = None) -> dict[str, Any]: ...

    def list_messages(
        self, conversation_id: str, limit: int = 200, cursor: str | None = None
    ) -> dict[str, Any]: ...


class ReadGatewayError(ImporterError):
    """Read-only gateway API failed or returned an invalid response."""


class ReadGatewayAuthError(ReadGatewayError):
    """MIC gateway rejected read credentials; retrying cannot repair this."""


class ReadGatewayTransientError(ReadGatewayError):
    """MIC gateway read failed transiently and may succeed on a later sweep."""


class MicReadClient:
    """Authenticated read-only MIC API client. It never uses the send credential."""

    def __init__(
        self,
        base_url: str,
        read_api_key: str,
        *,
        opener: Callable[..., Any] | None = None,
        timeout: float = 15,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.read_api_key = read_api_key
        self.opener = opener or urllib.request.build_opener(_NoRedirectHandler()).open
        self.timeout = timeout

    def list_conversations(
        self, limit: int = 200, cursor: str | None = None, updated_after: str | None = None
    ) -> dict[str, Any]:
        query: dict[str, str | int] = {"limit": limit}
        if cursor:
            query["cursor"] = cursor
        if updated_after:
            query["updated_after"] = updated_after
        return self._request("/v1/conversations?" + urllib.parse.urlencode(query))

    def list_messages(
        self, conversation_id: str, limit: int = 200, cursor: str | None = None
    ) -> dict[str, Any]:
        query: dict[str, str | int] = {"limit": limit}
        if cursor:
            query["cursor"] = cursor
        path = f"/v1/conversations/{urllib.parse.quote(conversation_id, safe='')}/messages"
        return self._request(path + "?" + urllib.parse.urlencode(query))

    def _request(self, path: str) -> dict[str, Any]:
        request = urllib.request.Request(
            self.base_url + path,
            headers={"X-API-Key": self.read_api_key, "Accept": "application/json"},
            method="GET",
        )
        try:
            response = self.opener(request, timeout=self.timeout)
            status = int(getattr(response, "status", 200))
            raw = response.read()
        except urllib.error.HTTPError as exc:
            _raise_gateway_status(exc.code)
        except (TimeoutError, OSError, urllib.error.URLError):
            raise ReadGatewayTransientError("MIC gateway transport failed") from None
        if status < 200 or status >= 300:
            _raise_gateway_status(status)
        try:
            value = json.loads(raw)
        except (json.JSONDecodeError, UnicodeDecodeError):
            raise ReadGatewayError("MIC gateway returned invalid JSON") from None
        if not isinstance(value, dict):
            raise ReadGatewayError("MIC gateway returned an invalid response")
        return value


def _raise_gateway_status(status: int) -> None:
    if status in (401, 403):
        raise ReadGatewayAuthError(f"MIC gateway returned HTTP {status}")
    if status == 429 or status >= 500:
        raise ReadGatewayTransientError(f"MIC gateway returned HTTP {status}")
    raise ReadGatewayError(f"MIC gateway returned HTTP {status}")


class ImportCrm(Protocol):
    def sync_batch(self, payload: Mapping[str, Any], request_id: str) -> CrmSyncResult: ...


class ImportState(Protocol):
    def checkpoint(self, resource: str) -> str | None: ...

    def stage_batch(
        self,
        resource: str,
        *,
        start_cursor: str | None,
        next_cursor: str | None,
        request_id: str,
        payload: dict[str, Any],
    ) -> None: ...

    def pending_batch(self, resource: str) -> dict[str, str | None | bool] | None: ...

    def mark_pending_conflict(self, resource: str, request_id: str) -> None: ...

    def confirm_batch(self, resource: str, request_id: str, result: CrmSyncResult) -> None: ...


class IncompleteHistoryError(ImporterError):
    """History completeness is false or absent on a MIC conversation."""


class ImportResult:
    def __init__(self, conversations: int = 0, messages: int = 0, batches: int = 0) -> None:
        self.conversations = conversations
        self.messages = messages
        self.batches = batches
        self.action_required_codes: list[str] = []

    def add(self, other: ImportResult) -> None:
        self.conversations += other.conversations
        self.messages += other.messages
        self.batches += other.batches
        self.action_required_codes.extend(other.action_required_codes)

    def __repr__(self) -> str:
        return (
            f"ImportResult(conversations={self.conversations}, messages={self.messages}, "
            f"batches={self.batches})"
        )


class MicCrmImporter:
    """Read complete MIC history and send account-scoped, replay-safe CRM batches."""

    def __init__(
        self,
        gateway: ReadGateway,
        crm: ImportCrm,
        state: ImportState,
        *,
        account_handle: str,
        batch_size: int = 100,
    ) -> None:
        if not account_handle.strip():
            raise ValueError("MIC account handle is required")
        if not 1 <= batch_size <= 100:
            raise ValueError("batch_size must be between 1 and 100")
        self.gateway = gateway
        self.crm = crm
        self.state = state
        self.account_handle = account_handle
        self.batch_size = batch_size

    @classmethod
    def from_config(
        cls,
        *,
        config: CrmBridgeConfig,
        crm: CrmClient,
        state: CrmBridgeState,
    ) -> MicCrmImporter:
        config.validate()
        return cls(
            MicReadClient(config.mic_base_url, config.mic_read_api_key),
            crm,
            state,
            account_handle=config.account_handle,
        )

    def backfill(self) -> ImportResult:
        return self._run(mode="backfill")

    def once(self) -> ImportResult:
        return self._run(mode="once")

    def _run(self, *, mode: str) -> ImportResult:
        for pending_resource in ("conversations", "conversations:once"):
            pending = self.state.pending_batch(pending_resource)
            if pending is not None and pending.get("conflict") is True:
                raise PendingBatchConflictError(
                    pending_resource,
                    str(pending.get("request_id") or ""),
                )
        if mode == "backfill":
            resource = "conversations"
            cursor = self.state.checkpoint(resource)
            if cursor == _COMPLETE_CURSOR:
                return ImportResult()
            start_checkpoint = cursor
        else:
            resource = "conversations:once"
            start_checkpoint = self.state.checkpoint(resource)
            cursor = None

        result = ImportResult()
        job_id = _job_id(self.account_handle, mode)
        conversation_aliases: dict[str, str] = {}
        seen_cursors: set[str] = set()
        page_count = 0
        checkpoint_blocked = False
        while True:
            page_count += 1
            if page_count > 10_000:
                raise ReadGatewayError("MIC conversation pagination exceeded the safety limit")
            page = self.gateway.list_conversations(limit=200, cursor=cursor)
            conversations = _page_items(page, "conversations")
            next_cursor = _cursor(page)
            if next_cursor is not None:
                if next_cursor in seen_cursors:
                    raise ReadGatewayError("MIC conversation pagination cursor repeated")
                seen_cursors.add(next_cursor)
            for index, conversation in enumerate(conversations):
                if not isinstance(conversation, dict):
                    raise ReadGatewayError("MIC gateway returned an invalid conversation")
                complete = index == len(conversations) - 1
                try:
                    outcome = self._import_conversation(
                        conversation,
                        mode=mode,
                        job_id=job_id,
                        resource=resource,
                        start_checkpoint=start_checkpoint,
                        page_next_cursor=next_cursor,
                        page_complete=complete,
                        final_page=next_cursor is None,
                        can_advance_cursor=not checkpoint_blocked,
                        conversation_aliases=conversation_aliases,
                    )
                except SourceIdentityAliasError:
                    # Continue importing other conversations, but retain the old page cursor
                    # so this conversation is retried after its identity needs operator review.
                    checkpoint_blocked = True
                    result.action_required_codes.append("source_identity_alias_unavailable")
                    continue
                result.add(outcome)
                start_checkpoint = self.state.checkpoint(resource)
            cursor = next_cursor
            if cursor is None:
                break
            # Once an unsafe identity has appeared, never advance past its page or a later
            # page. Idempotent replays are preferable to silently skipping one source record.
            if not checkpoint_blocked:
                start_checkpoint = self.state.checkpoint(resource)
        return result

    def _import_conversation(
        self,
        conversation: dict[str, Any],
        *,
        mode: str,
        job_id: str,
        resource: str,
        start_checkpoint: str | None,
        page_next_cursor: str | None,
        page_complete: bool,
        final_page: bool,
        can_advance_cursor: bool,
        conversation_aliases: dict[str, str],
    ) -> ImportResult:
        if conversation.get("history_complete") is not True:
            raise IncompleteHistoryError("MIC conversation history_complete is not true")
        gateway_id = _required_text(conversation.get("id"), "gateway conversation ID")
        raw_source_id = _required_text(conversation.get("source_id"), "MIC conversation source ID")
        source_id = _crm_external_id(
            raw_source_id,
            self.account_handle,
            used_aliases=conversation_aliases,
        )
        buyer_ref = _required_text(conversation.get("buyer_reference"), "MIC buyer_reference")
        if buyer_ref == "EEnxEJQbMJmm":
            buyer_ref = raw_source_id
        messages = self._all_messages(gateway_id)
        normalized = _normalize_messages(self.account_handle, raw_source_id, messages)
        batches = [
            normalized[i : i + self.batch_size] for i in range(0, len(normalized), self.batch_size)
        ]
        if not batches:
            batches = [[]]
        batch_result = ImportResult(conversations=1, messages=len(normalized))
        for index, batch in enumerate(batches, 1):
            final_for_conversation = index == len(batches)
            final_cursor = page_next_cursor if can_advance_cursor else start_checkpoint
            if final_for_conversation and page_complete and final_page and can_advance_cursor:
                final_cursor = _COMPLETE_CURSOR
            next_checkpoint = (
                final_cursor if final_for_conversation and page_complete else start_checkpoint
            )
            raw_buyer_name = conversation.get("buyer_name")
            if (
                isinstance(raw_buyer_name, str)
                and raw_buyer_name.strip()
                and raw_buyer_name.strip() != f"MIC 买家 {buyer_ref}"
            ):
                buyer_name = raw_buyer_name.strip()[:255]
                buyer_name_is_placeholder = False
            else:
                buyer_name = f"MIC 买家 {buyer_ref}"
                buyer_name_is_placeholder = True

            batch_payload: dict[str, Any] = {
                "jobId": job_id,
                "requestId": "",
                "accountHandle": self.account_handle,
                "syncMode": "incremental" if mode == "once" else "backfill",
                "batchNo": index,
                "finalBatch": final_for_conversation,
                "conversation": {
                    "sourceId": source_id,
                    "buyerExternalId": buyer_ref,
                    "buyerName": buyer_name,
                    "buyerNameIsPlaceholder": buyer_name_is_placeholder,
                    "subject": str(conversation.get("inquiry_subject") or "")[:255],
                    "country": str(conversation.get("country") or ""),
                    "unreadCount": int(
                        conversation.get("unread_count")
                        or (1 if conversation.get("unread") is True else 0)
                    ),
                },
                "messages": batch,
            }
            request_id = _stable_id(job_id, source_id, str(index), _canonical_hash(batch_payload))
            batch_payload["requestId"] = request_id
            self._check_pending_conflict(
                resource,
                start_cursor=start_checkpoint,
                next_cursor=next_checkpoint,
                request_id=request_id,
                payload=batch_payload,
            )
            self.state.stage_batch(
                resource,
                start_cursor=start_checkpoint,
                next_cursor=next_checkpoint,
                request_id=request_id,
                payload=batch_payload,
            )
            verified = self.crm.sync_batch(batch_payload, request_id)
            if verified.request_id != request_id or verified.response.get("accepted") is not True:
                raise ImporterError("CRM did not confirm the requested MIC batch")
            self.state.confirm_batch(resource, request_id, verified)
            batch_result.batches += 1
            start_checkpoint = self.state.checkpoint(resource)
        return batch_result

    def _check_pending_conflict(
        self,
        resource: str,
        *,
        start_cursor: str | None,
        next_cursor: str | None,
        request_id: str,
        payload: dict[str, Any],
    ) -> None:
        pending = self.state.pending_batch(resource)
        if pending is None:
            return
        previous_request_id = str(pending.get("request_id") or "")
        if pending.get("conflict") is True:
            raise PendingBatchConflictError(resource, previous_request_id)
        matches = (
            pending.get("start_cursor") == start_cursor
            and pending.get("next_cursor") == next_cursor
            and previous_request_id == request_id
            and pending.get("payload_sha256") == _canonical_hash(payload)
        )
        if not matches:
            self.state.mark_pending_conflict(resource, previous_request_id)
            raise PendingBatchConflictError(resource, previous_request_id)

    def _all_messages(self, conversation_id: str) -> list[dict[str, Any]]:
        cursor: str | None = None
        rows: list[dict[str, Any]] = []
        seen_cursors: set[str] = set()
        page_count = 0
        while True:
            page_count += 1
            if page_count > 10_000:
                raise ReadGatewayError("MIC message pagination exceeded the safety limit")
            page = self.gateway.list_messages(conversation_id, limit=200, cursor=cursor)
            rows.extend(_page_items(page, "messages"))
            cursor = _cursor(page)
            if cursor is None:
                return rows
            if cursor in seen_cursors:
                raise ReadGatewayError("MIC message pagination cursor repeated")
            seen_cursors.add(cursor)


def _normalize_messages(
    account_handle: str, source_id: str, messages: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    if any(not isinstance(message, dict) for message in messages):
        raise ReadGatewayError("MIC gateway returned an invalid message")
    valid = messages
    valid.sort(
        key=lambda message: (
            _sort_sequence(message.get("source_sequence")),
            str(message.get("source_timestamp_raw") or ""),
            str(message.get("id") or ""),
        )
    )
    counts: Counter[str] = Counter()
    used_aliases: dict[str, str] = {}
    output: list[dict[str, Any]] = []
    for index, message in enumerate(valid):
        direction = str(message.get("direction") or "").lower()
        if direction not in {"inbound", "outbound"}:
            raise ReadGatewayError("MIC message direction is invalid")
        attachment_metadata = _safe_attachment_metadata(message.get("attachment_metadata"))
        raw_id = str(message.get("source_id") or "").strip()
        if raw_id:
            external_id = _crm_external_id(raw_id, account_handle, used_aliases=used_aliases)
        else:
            signature = _canonical_hash(
                {
                    "account": account_handle,
                    "conversation": source_id,
                    "direction": direction,
                    "body": " ".join(str(message.get("content") or "").split()),
                    "timestamp": str(message.get("source_timestamp_raw") or ""),
                    "sender": str(message.get("sender_label") or ""),
                    "attachments": attachment_metadata["items"],
                }
            )
            counts[signature] += 1
            external_id = f"mic-fingerprint:{signature}:{counts[signature]}"
            previous_raw_id = used_aliases.get(external_id)
            fingerprint_identity = f"fingerprint:{signature}:{counts[signature]}"
            if previous_raw_id is not None and previous_raw_id != fingerprint_identity:
                raise SourceIdentityAliasError()
            used_aliases[external_id] = fingerprint_identity
        message_type = str(message.get("message_type") or "")
        if message_type not in {"initialInquiry", "chat"}:
            message_type = "initialInquiry" if index == 0 and direction == "inbound" else "chat"
        confidence = str(message.get("source_timestamp_confidence") or "low")
        if confidence not in {"high", "medium", "low"}:
            confidence = "low"
        output.append(
            {
                "externalId": external_id,
                "sourceSequence": message.get("source_sequence") or index + 1,
                "direction": direction,
                "messageType": message_type,
                "body": str(message.get("content") or ""),
                "senderName": _safe_sender_name(message.get("sender_label")),
                "attachmentMetadata": attachment_metadata,
                "sourceTimestampRaw": str(message.get("source_timestamp_raw") or ""),
                "timestampConfidence": confidence,
            }
        )
    return output


def _crm_external_id(
    source_id: str,
    account_handle: str,
    *,
    used_aliases: dict[str, str],
    maximum_length: int = 191,
) -> str:
    try:
        source_id.encode("utf-8")
        alias = source_id
        if len(source_id) > maximum_length or source_id.startswith("mic-sha256:"):
            digest = hashlib.sha256(f"{account_handle}\x00{source_id}".encode()).hexdigest()
            alias = f"mic-sha256:{digest}"
    except UnicodeEncodeError:
        raise SourceIdentityAliasError() from None
    if len(alias) > maximum_length:
        raise SourceIdentityAliasError()
    previous_source_id = used_aliases.get(alias)
    if previous_source_id is not None and previous_source_id != source_id:
        raise SourceIdentityAliasError()
    used_aliases[alias] = source_id
    return alias


def _safe_sender_name(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    sender = value.strip()
    return sender[:255] or None


def _safe_attachment_metadata(value: Any) -> dict[str, list[dict[str, Any]]]:
    if not isinstance(value, list):
        return {"items": []}
    items: list[dict[str, Any]] = []
    for attachment in value[:20]:
        if not isinstance(attachment, dict):
            continue
        name_value = attachment.get("name")
        if not isinstance(name_value, str) or not name_value.strip():
            continue
        name = name_value.strip()[:255]
        media_value = attachment.get("mediaType")
        media_type = (
            media_value.strip()[:100]
            if isinstance(media_value, str) and media_value.strip()
            else None
        )
        size_value = attachment.get("size")
        size: int | None = None
        if isinstance(size_value, int) and not isinstance(size_value, bool):
            if 0 <= size_value <= 2**63 - 1:
                size = size_value
        elif isinstance(size_value, str) and len(size_value) <= 19 and size_value.isdecimal():
            parsed_size = int(size_value)
            if parsed_size <= 2**63 - 1:
                size = parsed_size
        items.append({"name": name, "mediaType": media_type, "size": size})
    return {"items": items}


def _page_items(page: dict[str, Any], label: str) -> list[Any]:
    rows = page.get("items")
    if not isinstance(rows, list):
        raise ReadGatewayError(f"MIC gateway returned an invalid {label} page")
    return rows


def _cursor(page: dict[str, Any]) -> str | None:
    value = page.get("next_cursor")
    return str(value) if value not in (None, "") else None


def _required_text(value: Any, label: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ReadGatewayError(f"MIC source is missing {label}")
    return text


def _sort_sequence(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 2**31 - 1


def _canonical_hash(value: Mapping[str, Any]) -> str:
    serialized = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _stable_id(*parts: str) -> str:
    return "mic-" + hashlib.sha256("\x00".join(parts).encode("utf-8")).hexdigest()[:40]


def _job_id(account_handle: str, mode: str) -> str:
    return f"mic-{mode}-" + hashlib.sha256(account_handle.encode("utf-8")).hexdigest()[:16]


class _NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(
        self, req: Any, fp: Any, code: int, msg: str, headers: Any, newurl: str
    ) -> None:
        return None
