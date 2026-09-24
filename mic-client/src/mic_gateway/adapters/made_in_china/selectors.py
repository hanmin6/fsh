from __future__ import annotations

from dataclasses import dataclass

MEMBERCENTER_ORIGIN = "https://membercenter.made-in-china.com"


@dataclass(frozen=True, slots=True)
class ReadContract:
    name: str
    page_path: str
    response_path: str
    required_body_keys: frozenset[str]
    page_marker: str
    item_selector: str
    empty_selector: str | None


ORDERS = ReadContract(
    name="order_list",
    page_path="/newtrade/order/page/list.html",
    response_path="/api/newtrade/order/list",
    required_body_keys=frozenset({"code", "content", "successful"}),
    page_marker="#root-seller-list .sts-order-list",
    item_selector="#root-seller-list [data-order-id]",
    empty_selector="#root-seller-list .no-data-box",
)

CONVERSATIONS = ReadContract(
    name="conversation_list",
    page_path="/message/index.html",
    response_path="/message.do",
    required_body_keys=frozenset({"total", "unread", "unreply", "messages", "time"}),
    page_marker=".J-inquiry-layout",
    item_selector=".J-inquiry-item",
    empty_selector=None,
)

MESSAGES = ReadContract(
    name="message_list",
    page_path="/message/index.html",
    response_path="/message.do",
    required_body_keys=CONVERSATIONS.required_body_keys,
    page_marker=CONVERSATIONS.page_marker,
    item_selector=CONVERSATIONS.item_selector,
    empty_selector=None,
)

AUTHENTICATED_MARKERS = (
    CONVERSATIONS.page_marker,
    ".J-top-username",
    "a[href*='/message/index.html']",
)
LOGIN_MARKERS = (
    "input[type='password']",
    "form[action*='login']",
    ".J-top-unlogin:not([style*='display:none'])",
)
VERIFICATION_MARKERS = (
    "iframe[src*='captcha']",
    "iframe[src*='verify']",
    "[class*='captcha']",
    "[id*='captcha']",
)

CONVERSATION_ID_INPUT = "input.J-list-checkbox[id]"
CONVERSATION_LINK = "a.inquiry-content-go-bomDetail"
CONVERSATION_SUBJECT = ".J-inquiry-title .cnt-txt-link, .J-inquiry-title"
CONVERSATION_SUMMARY = ".tag-summer"
CHAT_ROOT = "#inquiryDetailReactWrap"
CHAT_SCROLL_REGION = f"{CHAT_ROOT} .tm-message-list"
CHAT_INIT_ERROR = f"{CHAT_ROOT} .init-error"
HISTORY_LOAD_BUTTON = f"{CHAT_ROOT} .tm-message-list-load-btn"
HISTORY_LOAD_LABEL = "load earlier messages"
HISTORY_LOAD_LABELS = frozenset({HISTORY_LOAD_LABEL, "查看更多消息"})
MESSAGE_HISTORY_MAX_CLICKS = 50
MESSAGE_HISTORY_PROGRESS_TIMEOUT_MS = 3_000
MESSAGE_HISTORY_PROGRESS_POLL_MS = 100
CHAT_RENDERED_ID_MARKER = f"{CHAT_ROOT} button.btn-reply[inquiry-id]"
MESSAGE_HISTORY_CONTROL_MOUNT_TIMEOUT_MS = 3_000
MESSAGE_HISTORY_CONTROL_POLL_MS = 100
MESSAGE_HISTORY_SCROLL_SETTLE_POLLS = 20
REPLY_BUTTON_SELECTORS = (
    ".btn-reply",
    "button.btn-reply",
    "button:has-text('回复')",
    "a:has-text('回复')",
)
COMPOSER_SELECTORS = (
    "#tm-message-input textarea.edit-area",
    ".tm-message-input textarea",
    "textarea.edit-area",
    f"{CHAT_ROOT} textarea",
    f"{CHAT_ROOT} [contenteditable='true']",
)
SEND_BUTTON_SELECTORS = (
    "button.tm-message-input-send",
    ".tm-message-input-send-box button",
    "#tm-message-input button:has-text('发 送')",
    "#tm-message-input button:has-text('发送')",
    f"{CHAT_ROOT} button.send-btn",
    f"{CHAT_ROOT} button.J-send",
    f"{CHAT_ROOT} [role='button'][data-action='send']",
)
OUTBOUND_MESSAGE_SELECTORS = (
    ".tm-message.tm-message-send .tm-message-content-text",
    ".tm-message.tm-message-send",
    f"{CHAT_ROOT} [data-direction='outbound']",
    f"{CHAT_ROOT} .message-item.is-self",
    f"{CHAT_ROOT} .msg-item.mine",
)

RESPONSE_TIMEOUT_MS = 20_000
PAGE_TIMEOUT_MS = 15_000
SESSION_DETECTION_TIMEOUT_MS = 10_000
SESSION_POLL_INTERVAL_MS = 200
