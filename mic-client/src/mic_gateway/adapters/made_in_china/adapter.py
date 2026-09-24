from __future__ import annotations

import asyncio
import hashlib
import json
import re
import time
from collections.abc import Mapping
from dataclasses import replace
from datetime import UTC, datetime, timedelta, timezone
from html.parser import HTMLParser
from typing import Any, cast
from urllib.parse import quote, unquote, urljoin, urlsplit

from playwright.async_api import TimeoutError as PlaywrightTimeoutError

from mic_gateway.adapters.base import (
    SendAttempt,
    SessionHealth,
    SourceCheckpoint,
    SourcePage,
)
from mic_gateway.adapters.made_in_china import selectors
from mic_gateway.browser.discovery import sanitize_capture
from mic_gateway.browser.runtime import BrowserRuntime
from mic_gateway.domain import (
    Direction,
    SourceConversation,
    SourceMessage,
    SourceOrder,
)

_SITE_TZ = timezone(timedelta(hours=8), name="Asia/Shanghai")


class SiteContractError(RuntimeError):
    """The seller portal no longer matches a reviewed contract."""


def _mapping(value: object, contract: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise SiteContractError(f"{contract}: expected object")
    return cast(Mapping[str, Any], value)


def _capture_body(value: Mapping[str, Any], contract: str) -> Mapping[str, Any]:
    body = value.get("body", value)
    return _mapping(body, contract)


def _required(body: Mapping[str, Any], keys: frozenset[str], contract: str) -> None:
    missing = sorted(keys.difference(body))
    if missing:
        raise SiteContractError(f"{contract}: missing {','.join(missing)}")


def _string(value: object, field: str, contract: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise SiteContractError(f"{contract}: invalid {field}")
    return value.strip()


def _optional_string(value: object) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None


def _site_datetime(value: object, field: str, contract: str) -> datetime:
    text = _string(value, field, contract)
    parsed: datetime | None = None
    for format_string in (
        "%Y%m%d%H%M%S",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y-%m-%d",
    ):
        try:
            parsed = datetime.strptime(text, format_string)
            break
        except ValueError:
            continue
    if parsed is None:
        try:
            parsed = datetime.fromisoformat(text)
        except ValueError as exc:
            raise SiteContractError(f"{contract}: invalid {field}") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=_SITE_TZ)
    return parsed.astimezone(UTC)


def _source_timestamp_confidence(value: object) -> str:
    text = _optional_string(value)
    if text is None:
        return "low"
    if re.fullmatch(
        r"(?:\d{14}|\d{4}-\d{2}-\d{2}[ T]\d{1,2}:\d{2}"
        r"(?::\d{2}(?:\.\d+)?)?(?:Z|[+-]\d{2}:?\d{2})?)",
        text,
    ):
        return "high"
    if re.fullmatch(r"(?:\d{4}-\d{2}-\d{2}|\d{8})", text):
        return "medium"
    return "low"


def _safe_snapshot(value: Mapping[str, Any]) -> dict[str, Any]:
    sanitized = sanitize_capture(dict(value))
    if not isinstance(sanitized, dict):
        raise SiteContractError("snapshot_sanitization_failed")
    return cast(dict[str, Any], sanitized)


def parse_orders(value: Mapping[str, Any]) -> SourcePage[SourceOrder]:
    body = _capture_body(value, selectors.ORDERS.name)
    _required(body, selectors.ORDERS.required_body_keys, selectors.ORDERS.name)
    if body.get("successful") is not True or body.get("code") != 0:
        raise SiteContractError("order_list: unsuccessful response")
    content = _mapping(body.get("content"), selectors.ORDERS.name)
    _required(
        content,
        frozenset(
            {"items", "currentPage", "currentPageSize", "totalPage", "pageSize", "totalItem"}
        ),
        selectors.ORDERS.name,
    )
    items = content.get("items")
    if not isinstance(items, list):
        raise SiteContractError("order_list: items must be an array")
    if items:
        # The authorized account had no orders during discovery. Parsing an unseen
        # paid-order shape would be more dangerous than pausing for fixture review.
        raise SiteContractError("order_list_nonempty_unreviewed")
    return SourcePage(items=(), next_cursor=None)


def parse_conversations(value: Mapping[str, Any]) -> SourcePage[SourceConversation]:
    body = _capture_body(value, selectors.CONVERSATIONS.name)
    _required(body, selectors.CONVERSATIONS.required_body_keys, selectors.CONVERSATIONS.name)
    raw_items = body.get("messages")
    if not isinstance(raw_items, list):
        raise SiteContractError("conversation_list: messages must be an array")
    result: list[SourceConversation] = []
    for raw in raw_items:
        item = _mapping(raw, selectors.CONVERSATIONS.name)
        source_id = _string(item.get("id"), "id", selectors.CONVERSATIONS.name)
        updated_at = _site_datetime(
            item.get("time", body.get("time")), "time", selectors.CONVERSATIONS.name
        )
        is_read = item.get("isRead")
        if not isinstance(is_read, bool):
            raise SiteContractError("conversation_list: invalid isRead")
        result.append(
            SourceConversation(
                source_id=source_id,
                buyer_reference=_optional_string(item.get("contactNo")),
                inquiry_subject=_optional_string(item.get("subject")),
                unread=not is_read,
                last_message_at=updated_at,
                source_updated_at=updated_at,
                raw_snapshot=_safe_snapshot(item),
            )
        )
    return SourcePage(items=tuple(result), next_cursor=None)


def parse_messages(
    value: Mapping[str, Any], *, conversation_source_id: str
) -> SourcePage[SourceMessage]:
    body = _capture_body(value, selectors.MESSAGES.name)
    _required(body, selectors.MESSAGES.required_body_keys, selectors.MESSAGES.name)
    raw_items = body.get("messages")
    if not isinstance(raw_items, list):
        raise SiteContractError("message_list: messages must be an array")
    result: list[SourceMessage] = []
    for raw in raw_items:
        item = _mapping(raw, selectors.MESSAGES.name)
        source_id = _string(item.get("id"), "id", selectors.MESSAGES.name)
        if source_id != conversation_source_id:
            continue
        timestamp_raw = item.get("time", body.get("time"))
        attachments = item.get("attachList", [])
        if not isinstance(attachments, list):
            raise SiteContractError("message_list: attachList must be an array")
        safe_attachments: list[dict[str, Any]] = []
        for attachment in attachments:
            safe_attachments.append(_safe_snapshot(_mapping(attachment, selectors.MESSAGES.name)))
        result.append(
            SourceMessage(
                source_id=f"{source_id}:inquiry",
                conversation_source_id=conversation_source_id,
                direction=Direction.INBOUND,
                sender_label=_optional_string(item.get("contactName")),
                content=_string(item.get("content"), "content", selectors.MESSAGES.name),
                attachment_metadata=tuple(safe_attachments),
                source_created_at=_site_datetime(
                    timestamp_raw, "time", selectors.MESSAGES.name
                ),
                raw_snapshot=_safe_snapshot(item),
                source_timestamp_raw=(
                    timestamp_raw if isinstance(timestamp_raw, str) else None
                ),
                source_sequence=1,
                source_timestamp_confidence=_source_timestamp_confidence(timestamp_raw),
            )
        )
    return SourcePage(items=tuple(result), next_cursor=None)


class _DomNode:
    def __init__(self, tag: str, attrs: dict[str, str | None]) -> None:
        self.tag = tag
        self.attrs = attrs
        self.children: list[_DomNode | str] = []

    @property
    def classes(self) -> set[str]:
        return set((self.attrs.get("class") or "").split())

    def descendants(self) -> list[_DomNode]:
        found: list[_DomNode] = []
        for child in self.children:
            if isinstance(child, _DomNode):
                found.append(child)
                found.extend(child.descendants())
        return found

    def text(self) -> str:
        return "".join(
            child if isinstance(child, str) else child.text() for child in self.children
        )


class _MessageDomParser(HTMLParser):
    _VOID_TAGS = {
        "area",
        "base",
        "br",
        "col",
        "embed",
        "hr",
        "img",
        "input",
        "link",
        "meta",
        "param",
        "source",
        "track",
        "wbr",
    }

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.root = _DomNode("document", {})
        self.stack = [self.root]

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        node = _DomNode(tag, dict(attrs))
        self.stack[-1].children.append(node)
        if tag not in self._VOID_TAGS:
            self.stack.append(node)

    def handle_endtag(self, tag: str) -> None:
        for index in range(len(self.stack) - 1, 0, -1):
            if self.stack[index].tag == tag:
                del self.stack[index:]
                break

    def handle_data(self, data: str) -> None:
        self.stack[-1].children.append(data)


def _normalized_message_text(text: str) -> str:
    return " ".join(text.replace("\u00a0", " ").split())


def _extract_dom_text_tokens(node: _DomNode) -> list[str]:
    tokens: list[str] = []
    for child in node.children:
        if isinstance(child, str):
            tokens.extend(child.split())
        else:
            tokens.extend(_extract_dom_text_tokens(child))
    return tokens


def _normalize_trade_messenger_time(
    tokens: list[str],
    ref_year: int,
) -> str | None:
    date_part = None
    time_part = None
    for token in tokens:
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", token):
            date_part = token
        elif re.fullmatch(r"\d{2}-\d{2}", token):
            date_part = f"{ref_year}-{token}"
        elif re.fullmatch(r"\d{1,2}:\d{2}(?::\d{2})?", token):
            time_part = token
    if date_part and time_part:
        return f"{date_part} {time_part}"
    if date_part:
        return date_part
    return None


def parse_trade_messenger_history(
    html: str,
    *,
    conversation_source_id: str,
    account_handle: str,
    history_complete: bool,
    reference_time: datetime | None = None,
) -> tuple[SourceMessage, ...]:
    """Parse rendered TradeMessenger bubbles after a caller has established completeness.

    This is an offline DOM parser only. It does not load earlier pages or infer that a
    visible snapshot contains full history; callers must prove that separately.
    """
    parser = _MessageDomParser()
    parser.feed(html)
    parser.close()
    nodes = parser.root.descendants()
    if any("init-error" in node.classes for node in nodes):
        raise SiteContractError("trademessenger_init_error")
    if not history_complete:
        raise SiteContractError("trademessenger_history_incomplete")
    bubbles = [node for node in nodes if "tm-message" in node.classes]
    if not bubbles:
        raise SiteContractError("trademessenger: no message bubbles")

    result: list[SourceMessage] = []
    fingerprint_occurrences: dict[str, int] = {}
    for node in bubbles:
        classes = node.classes
        if "tm-message-system" in classes:
            continue
        is_inbound = "tm-message-recv" in classes
        is_outbound = "tm-message-send" in classes
        if is_inbound == is_outbound:
            raise SiteContractError("trademessenger: unrecognized message direction")
        if is_inbound:
            direction = Direction.INBOUND
        else:
            direction = Direction.OUTBOUND

        descendants = node.descendants()
        content_node = next(
            (item for item in descendants if "tm-message-content" in item.classes), None
        )
        if content_node is None:
            raise SiteContractError("trademessenger: message content missing")
        text_node = next(
            (
                item
                for item in content_node.descendants()
                if "tm-message-content-text" in item.classes
            ),
            None,
        )
        content = _normalized_message_text((text_node or content_node).text())
        if not content:
            if any(
                "tm-message-content-image" in item.classes
                or "tm-limited-size-image" in item.classes
                for item in content_node.descendants()
            ) or any(item.tag == "img" for item in content_node.descendants()):
                content = "[图片]"
            elif any("inquiry-card" in item.classes for item in content_node.descendants()):
                content = "[询盘]"
            elif any("tm-message-content-file" in item.classes for item in content_node.descendants()):
                content = "[文件]"
            else:
                raise SiteContractError("trademessenger: empty message content")

        sender_node = next(
            (item for item in descendants if "tm-message-from-user-name" in item.classes), None
        )
        sender = _normalized_message_text(sender_node.text()) if sender_node else None
        time_node = next(
            (item for item in descendants if "tm-message-time-above-content" in item.classes), None
        )
        if time_node is None:
            raise SiteContractError("trademessenger: message time missing")
        time_tokens = _extract_dom_text_tokens(time_node)
        if not time_tokens:
            raise SiteContractError("trademessenger: message time missing")
        if all(isinstance(c, str) for c in time_node.children):
            time_raw = time_node.text()
        else:
            time_raw = " ".join(time_tokens)

        ref_year = (
            reference_time.year
            if reference_time is not None
            else datetime.now(_SITE_TZ).year
        )
        time_text = _normalize_trade_messenger_time(time_tokens, ref_year) or _normalized_message_text(time_raw)
        created_at = _site_datetime(time_text, "time", "trademessenger")
        timestamp_confidence = _source_timestamp_confidence(time_raw)

        attachments: list[dict[str, Any]] = []
        for attachment in content_node.descendants():
            attrs = attachment.attrs
            name = attrs.get("data-file-name") or attrs.get("data-attachment-name")
            if not name and "tm-message-attachment" in attachment.classes:
                name = _normalized_message_text(attachment.text()) or None
            if not name and "tm-message-content-image" in attachment.classes:
                img = next((d for d in attachment.descendants() if d.tag == "img"), None)
                src = (img.attrs.get("src") or "") if img else ""
                file_id = "image"
                if "fileid=" in src:
                    file_id = src.split("fileid=")[1].split("&")[0]
                attachments.append({
                    "name": f"{file_id}.jpg",
                    "mediaType": "image/jpeg",
                })
                continue
            if not name:
                continue
            metadata: dict[str, Any] = {"name": str(name)[:255]}
            media_type = attrs.get("data-media-type")
            size = attrs.get("data-file-size")
            if media_type:
                metadata["mediaType"] = str(media_type)[:100]
            if size and str(size).isdigit():
                metadata["size"] = int(str(size))
            attachments.append(metadata)

        sequence = len(result) + 1
        source_id = node.attrs.get("data-message-id")
        if not source_id:
            safe_attachments = json.dumps(
                attachments,
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
            )
            material = "\x1f".join(
                (
                    account_handle,
                    conversation_source_id,
                    direction.value,
                    time_raw,
                    _normalize_text_loose(content),
                    _normalize_text_loose(sender or ""),
                    safe_attachments,
                )
            )
            fingerprint = hashlib.sha256(material.encode("utf-8")).hexdigest()
            occurrence = fingerprint_occurrences.get(fingerprint, 0) + 1
            fingerprint_occurrences[fingerprint] = occurrence
            source_id = f"tm-{fingerprint}-{occurrence}"
        result.append(
            SourceMessage(
                source_id=source_id,
                conversation_source_id=conversation_source_id,
                direction=direction,
                sender_label=sender,
                content=content,
                attachment_metadata=tuple(attachments),
                source_created_at=created_at,
                source_timestamp_raw=time_raw,
                source_sequence=sequence,
                source_timestamp_confidence=timestamp_confidence,
            )
        )
    if not result:
        raise SiteContractError("trademessenger: no inbound or outbound bubbles")
    return tuple(result)


def _normalize_text_loose(text: str) -> str:
    t = text.replace("\u00a0", " ").replace("’", "'").replace("`", "'")
    return " ".join(t.split()).casefold()


def _history_progress_marker(html: str) -> tuple[tuple[str, str], ...]:
    parser = _MessageDomParser()
    parser.feed(html)
    parser.close()
    return tuple(
        (node.attrs.get("data-message-id") or "", _normalized_message_text(node.text()))
        for node in parser.root.descendants()
        if "tm-message" in node.classes and "tm-message-system" not in node.classes
    )


def _matches_content(
    dom_text: str, expected_content: str, expected_digest: str | None = None
) -> bool:
    if expected_digest and _normalized_digest(dom_text) == expected_digest:
        return True
    dom_loose = _normalize_text_loose(dom_text)
    exp_loose = _normalize_text_loose(expected_content)
    if dom_loose == exp_loose or exp_loose in dom_loose or dom_loose in exp_loose:
        return True
    # Key excerpt check (first 30 characters)
    excerpt = exp_loose[:30]
    return bool(excerpt and excerpt in dom_loose)


def _normalized_digest(content: str) -> str:
    normalized = " ".join(content.split()).casefold()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _conversation_id_from_url(url: str) -> str | None:
    fragment = urlsplit(url).fragment
    if not fragment.startswith("inbox/"):
        return None
    route = fragment.removeprefix("inbox/")
    route_id, separator, suffix = route.partition("..")
    if separator and suffix != "from=list":
        return ""
    return unquote(route_id)


def _url_identifies_conversation(url: str, source_id: str) -> bool:
    return _conversation_id_from_url(url) == source_id


class MadeInChinaAdapter:
    def __init__(self, runtime: BrowserRuntime) -> None:
        self.runtime = runtime
        self._last_refresh_at: float = 0.0

    async def check_session(self) -> SessionHealth:
        async def operation(page: Any) -> SessionHealth:
            now = time.time()
            current_url = str(page.url).casefold()
            detected = await self._detect_session(page)
            if detected is not None and detected.requires_operator:
                return detected

            # Periodic refresh threshold: 300 seconds (5 minutes)
            # If the session is healthy and currently on the conversation page, but hasn't
            # been refreshed in > 300s, force a reload to refresh DOM and keep WebSocket alive.
            is_stale = (now - self._last_refresh_at) >= 300.0
            if (
                not current_url.startswith("about:")
                and selectors.CONVERSATIONS.page_path in current_url
                and not is_stale
            ):
                if detected is not None and detected.healthy:
                    return detected
            await page.goto(
                urljoin(
                    self.runtime.settings.seller_url,
                    selectors.CONVERSATIONS.page_path,
                ),
                wait_until="domcontentloaded",
            )
            health = await self._wait_for_session(page)
            if health.healthy:
                self._last_refresh_at = time.time()
            return health

        try:
            return await self.runtime.run_serialized(operation)
        except PlaywrightTimeoutError:
            return SessionHealth.unavailable("site_timeout")

    async def list_orders(
        self, checkpoint: SourceCheckpoint
    ) -> SourcePage[SourceOrder]:
        del checkpoint

        async def operation(page: Any) -> SourcePage[SourceOrder]:
            await self._require_session(page)
            capture = await self._read_contract(page, selectors.ORDERS)
            return parse_orders(capture)

        return await self.runtime.run_serialized(operation)

    async def list_conversations(
        self, checkpoint: SourceCheckpoint
    ) -> SourcePage[SourceConversation]:
        del checkpoint

        async def operation(page: Any) -> SourcePage[SourceConversation]:
            await self._require_session(page)
            capture = await self._read_contract(page, selectors.CONVERSATIONS)
            return parse_conversations(capture)

        return await self.runtime.run_serialized(operation)

    async def list_messages(
        self,
        conversation_source_id: str,
        checkpoint: SourceCheckpoint,
    ) -> SourcePage[SourceMessage]:
        del checkpoint

        async def operation(page: Any) -> SourcePage[SourceMessage]:
            await self._require_session(page)
            capture = await self._read_contract(page, selectors.MESSAGES)
            inquiry_page = parse_messages(
                capture, conversation_source_id=conversation_source_id
            )
            if len(inquiry_page.items) != 1:
                raise SiteContractError("message_list: inquiry missing or ambiguous")

            if not await self._open_conversation(page, conversation_source_id):
                raise SiteContractError("trademessenger_history_incomplete: conversation missing")
            if not await self._conversation_identity_confirmed(page, conversation_source_id):
                raise SiteContractError(
                    "trademessenger_history_incomplete: conversation identity unconfirmed"
                )
            await self._click_target_reply_button(page, conversation_source_id)
            history_html = await self._load_complete_trade_messenger_history(
                page, conversation_source_id
            )
            if not await self._conversation_identity_confirmed(page, conversation_source_id):
                raise SiteContractError(
                    "trademessenger_history_incomplete: conversation identity changed"
                )
            inquiry = inquiry_page.items[0]
            buyer_name, country, buyer_id = await self._extract_buyer_profile(page, inquiry=inquiry)
            bubbles = parse_trade_messenger_history(
                history_html,
                conversation_source_id=conversation_source_id,
                account_handle=urlsplit(self.runtime.settings.seller_url).hostname
                or "made-in-china-seller",
                history_complete=True,
                reference_time=inquiry.source_created_at,
            )
            combined = [inquiry]
            combined.extend(
                message
                for message in bubbles
                if message.source_id != inquiry.source_id
            )
            ordered = tuple(
                replace(message, source_sequence=index)
                for index, message in enumerate(combined, start=1)
            )
            if not await self._conversation_identity_confirmed(page, conversation_source_id):
                raise SiteContractError(
                    "trademessenger_history_incomplete: conversation identity changed"
                )
            return SourcePage(
                items=ordered,
                next_cursor=None,
                history_complete=True,
                buyer_name=buyer_name,
                country=country,
                buyer_id=buyer_id,
            )

        return await self.runtime.run_serialized(operation)

    async def _extract_buyer_profile(
        self, page: Any, *, inquiry: SourceMessage | None = None
    ) -> tuple[str | None, str | None, str | None]:
        buyer_name = None
        country = None
        buyer_id = None
        try:
            profile = await page.evaluate(
                r"""() => {
                    const nameEl = document.querySelector('.sd-card__name-text, .Mai_user_name');
                    const regionEl = document.querySelector('.sd-card__region, .Mai_flag');
                    const customerEl = document.querySelector('.sd-card__name[href*="customer-detail"], a[href*="customer-detail"], [href*="customer-detail"]');
                    let bName = nameEl ? (nameEl.innerText || '').trim() : null;
                    let cName = null;
                    let bId = null;
                    if (customerEl) {
                        const href = customerEl.getAttribute('href') || '';
                        const match = href.match(/customer-detail\/([a-zA-Z0-9_-]+)/);
                        if (match) bId = match[1].trim();
                    }
                    if (regionEl) {
                        cName = regionEl.getAttribute('data-mai') || (regionEl.innerText || '').trim();
                    }
                    if (!cName) {
                        const propEls = document.querySelectorAll('.inquiry-property');
                        for (const el of propEls) {
                            const text = (el.innerText || '').trim();
                            const match = text.match(/^([A-Za-z\\s]+)\\s*\\(/);
                            if (match) {
                                cName = match[1].trim();
                                break;
                            }
                        }
                    }
                    return { buyerName: bName, country: cName, buyerId: bId };
                }"""
            )
            if isinstance(profile, dict):
                raw_name = profile.get("buyerName")
                if isinstance(raw_name, str) and raw_name.strip():
                    buyer_name = raw_name.strip()
                raw_country = profile.get("country")
                if isinstance(raw_country, str) and raw_country.strip():
                    country = raw_country.strip()
                raw_id = profile.get("buyerId")
                if isinstance(raw_id, str) and raw_id.strip():
                    buyer_id = raw_id.strip()
        except Exception:
            pass

        if not buyer_name and inquiry and inquiry.sender_label:
            buyer_name = inquiry.sender_label.strip()

        return buyer_name or None, country or None, buyer_id or None

    async def _load_complete_trade_messenger_history(
        self, page: Any, conversation_source_id: str
    ) -> str:
        root = page.locator(selectors.CHAT_ROOT)

        async def read_chat_html() -> str:
            html = await root.inner_html()
            if not isinstance(html, str):
                raise SiteContractError("trademessenger_history_incomplete: invalid chat markup")
            return html

        try:
            await root.wait_for(state="visible", timeout=selectors.PAGE_TIMEOUT_MS)
        except PlaywrightTimeoutError as exc:
            raise SiteContractError("trademessenger_history_incomplete: chat root missing") from exc

        if not await self._conversation_identity_confirmed(page, conversation_source_id):
            raise SiteContractError(
                "trademessenger_history_incomplete: conversation identity unconfirmed"
            )

        history_html = await read_chat_html()
        mount_poll_count = max(
            1,
            selectors.MESSAGE_HISTORY_CONTROL_MOUNT_TIMEOUT_MS
            // selectors.MESSAGE_HISTORY_CONTROL_POLL_MS,
        )
        for _ in range(mount_poll_count):
            if await page.locator(selectors.CHAT_INIT_ERROR).count():
                raise SiteContractError("trademessenger_init_error")
            button = page.locator(selectors.HISTORY_LOAD_BUTTON)
            button_count = await button.count()
            if button_count > 1:
                raise SiteContractError(
                    "trademessenger_history_incomplete: load control ambiguous"
                )
            if button_count == 1 and await button.is_visible():
                label = _normalize_text_loose(await button.inner_text())
                if label not in selectors.HISTORY_LOAD_LABELS:
                    raise SiteContractError(
                        "trademessenger_history_incomplete: load control unrecognized"
                    )
                break
            await page.wait_for_timeout(selectors.MESSAGE_HISTORY_CONTROL_POLL_MS)
        else:
            scroll_region = page.locator(selectors.CHAT_SCROLL_REGION)
            if await scroll_region.count() != 1 or not await scroll_region.is_visible():
                raise SiteContractError(
                    "trademessenger_history_incomplete: load control readiness unverified"
                )
            return await self._load_history_by_scrolling(
                page, root, conversation_source_id
            )

        history_html = await read_chat_html()
        for clicks in range(selectors.MESSAGE_HISTORY_MAX_CLICKS + 1):
            if await page.locator(selectors.CHAT_INIT_ERROR).count():
                raise SiteContractError("trademessenger_init_error")
            if not await self._conversation_identity_confirmed(page, conversation_source_id):
                raise SiteContractError(
                    "trademessenger_history_incomplete: conversation identity changed"
                )

            button = page.locator(selectors.HISTORY_LOAD_BUTTON)
            button_count = await button.count()
            if button_count == 0:
                if clicks > 0 and len(before) <= 1 and _history_progress_marker(history_html) == before:
                    raise SiteContractError(
                        "trademessenger_history_incomplete: history_no_progress"
                    )
                if not await self._conversation_identity_confirmed(page, conversation_source_id):
                    raise SiteContractError(
                        "trademessenger_history_incomplete: conversation identity changed"
                    )
                return history_html
            if button_count != 1 or not await button.is_visible():
                raise SiteContractError("trademessenger_history_incomplete: load control ambiguous")
            label = _normalize_text_loose(await button.inner_text())
            if label not in selectors.HISTORY_LOAD_LABELS:
                raise SiteContractError(
                    "trademessenger_history_incomplete: load control unrecognized"
                )
            if clicks >= selectors.MESSAGE_HISTORY_MAX_CLICKS:
                raise SiteContractError(
                    "trademessenger_history_incomplete: history click bound reached"
                )

            before = _history_progress_marker(history_html)
            await button.click()
            poll_count = max(
                1,
                selectors.MESSAGE_HISTORY_PROGRESS_TIMEOUT_MS
                // selectors.MESSAGE_HISTORY_PROGRESS_POLL_MS,
            )
            for _ in range(poll_count):
                await page.wait_for_timeout(selectors.MESSAGE_HISTORY_PROGRESS_POLL_MS)
                history_html = await read_chat_html()
                if await page.locator(selectors.CHAT_INIT_ERROR).count():
                    raise SiteContractError("trademessenger_init_error")
                if not await self._conversation_identity_confirmed(
                    page, conversation_source_id
                ):
                    raise SiteContractError(
                        "trademessenger_history_incomplete: conversation identity changed"
                    )
                after = _history_progress_marker(history_html)
                if after != before:
                    break
                button_now = page.locator(selectors.HISTORY_LOAD_BUTTON)
                if await button_now.count() == 0 or not await button_now.first.is_visible():
                    if len(before) <= 1:
                        raise SiteContractError(
                            "trademessenger_history_incomplete: history_no_progress"
                        )
                    break
            else:
                raise SiteContractError(
                    "trademessenger_history_incomplete: history_no_progress"
                )

        raise SiteContractError("trademessenger_history_incomplete: history click bound reached")

    async def _load_history_by_scrolling(
        self,
        page: Any,
        root: Any,
        conversation_source_id: str,
        *,
        ignore_load_button: bool = False,
    ) -> str:
        """Read a chat that loads history on scroll and exposes no load button."""
        scroll_js = """(root, edge) => {
            let node = root.querySelector('.tm-message-list-messages') || root;
            let scroller = root;
            while (node) {
                if (node.scrollHeight > node.clientHeight + 2) {
                    scroller = node;
                    break;
                }
                if (node === root) break;
                node = node.parentElement;
            }
            scroller.scrollTop = edge === 'top' ? 0 : scroller.scrollHeight;
            return {top: scroller.scrollTop, height: scroller.scrollHeight,
                    client: scroller.clientHeight};
        }"""

        async def read_checked() -> str:
            if await page.locator(selectors.CHAT_INIT_ERROR).count():
                raise SiteContractError("trademessenger_init_error")
            if not await self._conversation_identity_confirmed(page, conversation_source_id):
                raise SiteContractError(
                    "trademessenger_history_incomplete: conversation identity changed"
                )
            html = await root.inner_html()
            if not isinstance(html, str):
                raise SiteContractError("trademessenger_history_incomplete: invalid chat markup")
            return html

        history_html = await read_checked()
        seen = set(_history_progress_marker(history_html))
        await root.evaluate(scroll_js, "bottom")
        await page.wait_for_timeout(selectors.MESSAGE_HISTORY_CONTROL_POLL_MS)
        history_html = await read_checked()
        current = set(_history_progress_marker(history_html))
        if not seen.issubset(current):
            raise SiteContractError("trademessenger_history_incomplete: virtualized messages")
        seen = current
        stable = 0
        pending_click_marker: set[tuple[str, str]] | None = None
        pending_click_polls = 0

        for _ in range(selectors.MESSAGE_HISTORY_MAX_CLICKS):
            metrics = await root.evaluate(scroll_js, "top")
            await page.wait_for_timeout(selectors.MESSAGE_HISTORY_CONTROL_POLL_MS)
            history_html = await read_checked()
            current = set(_history_progress_marker(history_html))
            if not seen.issubset(current):
                raise SiteContractError("trademessenger_history_incomplete: virtualized messages")
            if pending_click_marker is not None:
                if current == pending_click_marker:
                    pending_click_polls += 1
                    if pending_click_polls >= selectors.MESSAGE_HISTORY_SCROLL_SETTLE_POLLS:
                        ignore_load_button = True
                        pending_click_marker = None
                        pending_click_polls = 0
                        stable = 0
                    continue
                pending_click_marker = None
                pending_click_polls = 0
            if current != seen:
                seen = current
                stable = 0
                continue

            button = page.locator(selectors.HISTORY_LOAD_BUTTON)
            if not ignore_load_button and await button.count() == 1 and await button.is_visible():
                label = _normalize_text_loose(await button.inner_text())
                if label not in selectors.HISTORY_LOAD_LABELS:
                    raise SiteContractError(
                        "trademessenger_history_incomplete: load control unrecognized"
                    )
                await button.click()
                pending_click_marker = current
                pending_click_polls = 0
                stable = 0
                continue
            if not ignore_load_button and await button.count() > 1:
                raise SiteContractError(
                    "trademessenger_history_incomplete: load control ambiguous"
                )

            if not isinstance(metrics, dict) or metrics.get("top", 1) > 1:
                stable = 0
                continue
            stable += 1
            if stable < selectors.MESSAGE_HISTORY_SCROLL_SETTLE_POLLS:
                continue

            await root.evaluate(scroll_js, "bottom")
            await page.wait_for_timeout(selectors.MESSAGE_HISTORY_CONTROL_POLL_MS)
            final_html = await read_checked()
            final = set(_history_progress_marker(final_html))
            if not seen.issubset(final):
                raise SiteContractError("trademessenger_history_incomplete: virtualized messages")
            if final != seen:
                seen = final
                stable = 0
                continue
            return final_html

        raise SiteContractError("trademessenger_history_incomplete: scroll bound reached")

    async def send_message(
        self, conversation_source_id: str, content: str
    ) -> SendAttempt:
        async def operation(page: Any) -> SendAttempt:
            await self._require_session(page)

            opened = await self._open_conversation(page, conversation_source_id)
            if not opened:
                return SendAttempt.permanent_failure("conversation_not_found")

            if not await self._conversation_identity_confirmed(page, conversation_source_id):
                return SendAttempt.permanent_failure("conversation_identity_unconfirmed")

            composer = await self._first_visible(page, selectors.COMPOSER_SELECTORS)
            if composer is None:
                try:
                    await self._click_target_reply_button(page, conversation_source_id)
                except SiteContractError:
                    return SendAttempt.permanent_failure("conversation_identity_unconfirmed")

                for _ in range(20):
                    composer = await self._first_visible(page, selectors.COMPOSER_SELECTORS)
                    if composer is not None:
                        break
                    await page.wait_for_timeout(500)

            if composer is None:
                return SendAttempt.permanent_failure("composer_not_found")

            await composer.fill(content)
            await page.wait_for_timeout(500)

            send_button = await self._first_visible(page, selectors.SEND_BUTTON_SELECTORS)
            if send_button is None:
                send_button = page.locator(selectors.CHAT_ROOT).get_by_role(
                    "button", name=re.compile(r"^(发\s*送|send)$", re.IGNORECASE)
                )
                if await send_button.count() != 1 or not await send_button.is_visible():
                    return SendAttempt.permanent_failure("send_control_not_found")

            for _ in range(10):
                if not await send_button.is_disabled():
                    break
                await page.wait_for_timeout(300)

            if not await self._conversation_identity_confirmed(page, conversation_source_id):
                return SendAttempt.permanent_failure("conversation_identity_unconfirmed")

            send_time = datetime.now(UTC)
            await send_button.click()

            matched = None
            for _ in range(20):
                matched = await self._find_outbound_dom(
                    page,
                    conversation_source_id,
                    content,
                    send_time,
                )
                if matched is not None:
                    break
                await page.wait_for_timeout(500)

            if matched is None:
                return SendAttempt.uncertain("confirmation_missing")
            return SendAttempt.sent(matched.source_id)

        return await self.runtime.run_serialized(operation)

    async def find_outbound_match(
        self,
        conversation_source_id: str,
        content_digest: str,
        earliest: datetime,
    ) -> SourceMessage | None:
        async def operation(page: Any) -> SourceMessage | None:
            await self._require_session(page)
            if not await self._open_conversation(page, conversation_source_id):
                return None
            if not await self._conversation_identity_confirmed(page, conversation_source_id):
                return None
            return await self._find_outbound_dom(
                page,
                conversation_source_id,
                None,
                earliest,
                expected_digest=content_digest,
            )

        return await self.runtime.run_serialized(operation)

    async def _detect_session(self, page: Any) -> SessionHealth | None:
        current_url = str(page.url).casefold()
        if any(part in current_url for part in ("login.", "/sign-in", "/logon")):
            return SessionHealth.authentication_required()
        for marker in selectors.VERIFICATION_MARKERS:
            if await page.locator(marker).count() and await page.locator(marker).first.is_visible():
                return SessionHealth.verification_required()
        for marker in selectors.LOGIN_MARKERS:
            if await page.locator(marker).count() and await page.locator(marker).first.is_visible():
                return SessionHealth.authentication_required()
        for marker in selectors.AUTHENTICATED_MARKERS:
            if await page.locator(marker).count() and await page.locator(marker).first.is_visible():
                return SessionHealth.available()
        return None

    async def _wait_for_session(self, page: Any) -> SessionHealth:
        attempts = max(
            1,
            selectors.SESSION_DETECTION_TIMEOUT_MS
            // selectors.SESSION_POLL_INTERVAL_MS,
        )
        for attempt in range(attempts):
            health = await self._detect_session(page)
            if health is not None:
                if health.healthy:
                    self.runtime.mark_authenticated()
                elif health.requires_operator:
                    self.runtime.mark_operator_action_required()
                return health
            if attempt + 1 < attempts:
                await page.wait_for_timeout(selectors.SESSION_POLL_INTERVAL_MS)
        self.runtime.mark_site_contract_error()
        return SessionHealth.unavailable("site_contract_error")

    async def _require_session(self, page: Any) -> None:
        health = await self._wait_for_session(page)
        if not health.healthy:
            raise SiteContractError(health.detail_code or "session_unavailable")

    async def _read_contract(
        self, page: Any, contract: selectors.ReadContract
    ) -> dict[str, Any]:
        loop = asyncio.get_running_loop()
        found: asyncio.Future[dict[str, Any]] = loop.create_future()
        tasks: set[asyncio.Task[None]] = set()

        async def inspect(response: Any) -> None:
            if urlsplit(str(response.url)).path != contract.response_path:
                return
            if int(response.status) != 200:
                return
            content_type = str(response.headers.get("content-type", ""))
            if "json" not in content_type.casefold():
                return
            try:
                body = await response.json()
            except Exception:
                return
            if not isinstance(body, dict) or not contract.required_body_keys.issubset(body):
                return
            if not found.done():
                found.set_result(
                    {
                        "method": str(response.request.method),
                        "url": f"{urlsplit(str(response.url)).scheme}://"
                        f"{urlsplit(str(response.url)).netloc}{contract.response_path}",
                        "status": int(response.status),
                        "content_type": content_type,
                        # Normalize business fields from the authenticated response;
                        # each parser sanitizes only its raw_snapshot before storage.
                        "body": body,
                    }
                )

        def observe(response: Any) -> None:
            task = asyncio.create_task(inspect(response))
            tasks.add(task)
            task.add_done_callback(tasks.discard)

        page.on("response", observe)
        try:
            await page.goto(
                urljoin(self.runtime.settings.seller_url, contract.page_path),
                wait_until="domcontentloaded",
            )
            try:
                return await asyncio.wait_for(
                    found, timeout=selectors.RESPONSE_TIMEOUT_MS / 1000
                )
            except TimeoutError:
                return await self._dom_fallback(page, contract)
        finally:
            page.remove_listener("response", observe)
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)

    async def _dom_fallback(
        self, page: Any, contract: selectors.ReadContract
    ) -> dict[str, Any]:
        try:
            await page.locator(contract.page_marker).wait_for(
                state="visible", timeout=selectors.PAGE_TIMEOUT_MS
            )
        except PlaywrightTimeoutError as exc:
            raise SiteContractError(f"{contract.name}: page marker missing") from exc
        if contract is selectors.ORDERS:
            if contract.empty_selector and await page.locator(contract.empty_selector).is_visible():
                return {
                    "body": {
                        "code": 0,
                        "content": {
                            "items": [],
                            "currentPage": 0,
                            "currentPageSize": 0,
                            "totalPage": 0,
                            "pageSize": 0,
                            "totalItem": 0,
                        },
                        "message": None,
                        "successful": True,
                    }
                }
            raise SiteContractError("order_list_nonempty_unreviewed")
        rows = page.locator(contract.item_selector)
        count = await rows.count()
        if count == 0:
            raise SiteContractError(f"{contract.name}: no validated items or empty marker")
        now_text = datetime.now(_SITE_TZ).strftime("%Y-%m-%d %H:%M:%S")
        messages: list[dict[str, Any]] = []
        for index in range(count):
            row = rows.nth(index)
            identity = row.locator(selectors.CONVERSATION_ID_INPUT)
            if await identity.count() != 1:
                raise SiteContractError(f"{contract.name}: conversation id missing")
            source_id = await identity.get_attribute("id")
            buyer_reference = await identity.get_attribute("cid")
            subject = await row.locator(selectors.CONVERSATION_SUBJECT).first.inner_text()
            summary_locator = row.locator(selectors.CONVERSATION_SUMMARY)
            summary = (
                await summary_locator.first.inner_text()
                if await summary_locator.count()
                else subject
            )
            messages.append(
                {
                    "id": source_id,
                    "contactNo": buyer_reference,
                    "contactName": None,
                    "subject": subject,
                    "content": summary,
                    "time": now_text,
                    "isRead": "unread" not in (await row.get_attribute("class") or ""),
                    "attachList": [],
                }
            )
        return {
            "body": {
                "total": count,
                "unread": sum(not item["isRead"] for item in messages),
                "unreply": 0,
                "messages": messages,
                "time": now_text,
            }
        }

    async def _open_conversation(self, page: Any, source_id: str) -> bool:
        if not _url_identifies_conversation(str(page.url), source_id):
            conv_url = urljoin(
                self.runtime.settings.seller_url,
                "/message/index.html#inbox/"
                f"{quote(source_id, safe='').replace('.', '%2E')}..from=list",
            )
            await page.goto(conv_url, wait_until="domcontentloaded")
            await page.wait_for_timeout(2000)

        identities = page.locator(selectors.CONVERSATION_ID_INPUT)
        matching_rows = [
            index
            for index in range(await identities.count())
            if await identities.nth(index).get_attribute("id") == source_id
        ]
        if len(matching_rows) == 1:
            row = identities.nth(matching_rows[0])
            parent_row = row.locator("xpath=ancestor::tr[contains(@class, 'J-inquiry-item') or 1]")
            link = parent_row.locator(selectors.CONVERSATION_LINK)
            if await link.count() >= 1:
                try:
                    await link.first.click()
                    await page.wait_for_timeout(1000)
                except Exception:
                    pass

        try:
            await page.locator(selectors.CHAT_ROOT).first.wait_for(
                state="visible", timeout=selectors.PAGE_TIMEOUT_MS
            )
        except PlaywrightTimeoutError:
            return False
        return True

    async def _conversation_identity_confirmed(self, page: Any, source_id: str) -> bool:
        route_id = _conversation_id_from_url(str(page.url))
        if route_id is not None and route_id != source_id:
            return False
        try:
            markers = page.locator(selectors.CHAT_RENDERED_ID_MARKER)
            if await markers.count() != 1:
                return False
            marker = markers.first
            if await marker.get_attribute("inquiry-id") != source_id:
                return False
            return (await marker.is_visible()) is True
        except Exception:
            return False

    async def _click_target_reply_button(self, page: Any, source_id: str) -> None:
        if not await self._conversation_identity_confirmed(page, source_id):
            raise SiteContractError(
                "trademessenger_history_incomplete: conversation identity unconfirmed"
            )
        marker = page.locator(selectors.CHAT_RENDERED_ID_MARKER).first
        await marker.click()
        await page.wait_for_timeout(1000)
        if not await self._conversation_identity_confirmed(page, source_id):
            raise SiteContractError(
                "trademessenger_history_incomplete: conversation identity changed"
            )

    @staticmethod
    async def _first_visible(page: Any, candidates: tuple[str, ...]) -> Any | None:
        for selector in candidates:
            locator = page.locator(selector)
            if await locator.count() >= 1 and await locator.first.is_visible():
                return locator.first
        return None

    async def _find_outbound_dom(
        self,
        page: Any,
        conversation_source_id: str,
        content: str | None,
        earliest: datetime,
        *,
        expected_digest: str | None = None,
    ) -> SourceMessage | None:
        del earliest
        digest = expected_digest or (_normalized_digest(content or "") if content else None)
        pages_to_check = (
            list(page.context.pages)
            if hasattr(page, "context") and page.context and page.context.pages
            else [page]
        )
        for p in reversed(pages_to_check):
            for selector in selectors.OUTBOUND_MESSAGE_SELECTORS:
                messages = p.locator(selector)
                count = await messages.count()
                for index in range(count - 1, -1, -1):
                    item = messages.nth(index)
                    text = await item.inner_text()
                    matched = False
                    if content and _matches_content(text, content, digest):
                        matched = True
                    elif digest and _normalized_digest(text) == digest:
                        matched = True
                    if not matched:
                        continue
                    source_id = await item.get_attribute("data-message-id")
                    if not source_id:
                        dom = item.locator(
                            "xpath=ancestor-or-self::*[starts-with(@id, 'tm-message-')][1]"
                        )
                        if await dom.count() == 1:
                            dom_id = await dom.get_attribute("id")
                            if dom_id and dom_id.startswith("tm-message-"):
                                source_id = dom_id.removeprefix("tm-message-")
                    if not source_id:
                        source_id = f"outbound-{int(datetime.now(UTC).timestamp())}"
                    return SourceMessage(
                        source_id=source_id,
                        conversation_source_id=conversation_source_id,
                        direction=Direction.OUTBOUND,
                        sender_label="seller",
                        content=text,
                        attachment_metadata=(),
                        source_created_at=datetime.now(UTC),
                        raw_snapshot={},
                    )
        return None
