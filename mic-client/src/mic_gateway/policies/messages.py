from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

from mic_gateway.domain import MessageIntent

MAX_MESSAGE_LENGTH = 4_000

DEFAULT_BLOCK_PATTERNS = (
    r"(?:USD|EUR|CNY|RMB|GBP|JPY|CAD|AUD|HKD|\$|€|¥|￥)\s*\d",
    r"\d(?:[\d,.]*\d)?\s*(?:USD|EUR|CNY|RMB|GBP|JPY|CAD|AUD|HKD|美元|欧元|人民币|元)",
    r"\b(?:price|pricing|quotation|quote|discount)\b|价格|报价|折扣|打折|[一二三四五六七八九\d](?:\.\d+)?折",
    r"\b(?:payment|pay by|wire transfer|bank transfer|deposit|letter of credit)\b"
    r"|付款|支付|汇款|定金|信用证",
    r"\b(?:delivery|ship(?:ping)?)\b.{0,40}\b(?:within|by|guarantee|commit|days?|weeks?|months?)\b|(?:交货|发货|运输).{0,40}(?:天|周|月|保证|承诺|期限)",
    r"\b(?:in stock|stock available|production capacity|capacity)\b|库存|现货|产能|生产能力",
    r"\b(?:contract|warranty|guarantee terms?)\b|合同|保修|质保|保证条款",
    r"\b(?:refund|chargeback|dispute)\b|退款|退货|争议|纠纷",
)


class PolicyUnavailable(RuntimeError):
    """Raised when the configured policy cannot be evaluated safely."""


@dataclass(frozen=True, slots=True)
class MessagePolicyConfig:
    block_patterns: tuple[str, ...] = DEFAULT_BLOCK_PATTERNS
    max_content_length: int = MAX_MESSAGE_LENGTH


@dataclass(frozen=True, slots=True)
class PolicyDecision:
    allowed: bool
    code: str
    normalized_content: str


def normalize_content(content: str) -> str:
    normalized = unicodedata.normalize("NFKC", content)
    return " ".join(normalized.split())


def _compile_rules(config: MessagePolicyConfig) -> tuple[re.Pattern[str], ...]:
    if config.max_content_length <= 0 or not config.block_patterns:
        raise PolicyUnavailable("message policy configuration is invalid")
    try:
        if any(not pattern.strip() for pattern in config.block_patterns):
            raise PolicyUnavailable("message policy contains an empty rule")
        return tuple(re.compile(pattern, re.IGNORECASE) for pattern in config.block_patterns)
    except re.error as exc:
        raise PolicyUnavailable("message policy contains an invalid rule") from exc


def evaluate_message(
    intent: MessageIntent,
    content: str,
    *,
    config: MessagePolicyConfig | None = None,
) -> PolicyDecision:
    resolved = config or MessagePolicyConfig()
    rules = _compile_rules(resolved)
    normalized = normalize_content(content)
    if not normalized or len(normalized) > resolved.max_content_length:
        return PolicyDecision(False, "requires_human_review", normalized)
    if intent not in MessageIntent:
        return PolicyDecision(False, "requires_human_review", normalized)
    if any(rule.search(normalized) for rule in rules):
        return PolicyDecision(False, "requires_human_review", normalized)
    return PolicyDecision(True, "allowed", normalized)
