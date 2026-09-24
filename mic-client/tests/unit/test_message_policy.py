from __future__ import annotations

import pytest

from mic_gateway.domain import MessageIntent
from mic_gateway.policies.messages import (
    MessagePolicyConfig,
    PolicyUnavailable,
    evaluate_message,
)


@pytest.mark.parametrize(
    ("intent", "text"),
    [
        (MessageIntent.GREETING, "Hello, thank you for contacting us."),
        (MessageIntent.HOLIDAY_WISH, "Happy New Year 2027!"),
        (MessageIntent.ACKNOWLEDGEMENT, "收到您的消息，我们会由同事进一步跟进。"),
        (MessageIntent.NON_COMMERCIAL_FOLLOWUP, "Just checking whether you saw our note."),
    ],
)
def test_low_risk_messages_are_allowed(intent: MessageIntent, text: str) -> None:
    decision = evaluate_message(intent, text)

    assert decision.allowed is True
    assert decision.code == "allowed"


@pytest.mark.parametrize(
    "text",
    [
        "Our price is USD 12.50 each.",
        "可以给您九折",
        "Delivery will be within 7 days.",
        "Please pay by wire transfer.",
        "We guarantee 500 units in stock.",
        "We can issue a refund.",
        "合同和保修条款可以商量。",
        "We dispute that charge.",
    ],
)
def test_commercial_commitments_require_human_review(text: str) -> None:
    decision = evaluate_message(MessageIntent.NON_COMMERCIAL_FOLLOWUP, text)

    assert decision.allowed is False
    assert decision.code == "requires_human_review"


def test_unicode_and_whitespace_are_normalized_before_scanning() -> None:
    decision = evaluate_message(
        MessageIntent.NON_COMMERCIAL_FOLLOWUP,
        "Our  ｐｒｉｃｅ\n is   ＵＳＤ 12.50.",
    )

    assert decision.allowed is False
    assert decision.normalized_content == "Our price is USD 12.50."


def test_invalid_policy_configuration_fails_closed() -> None:
    with pytest.raises(PolicyUnavailable):
        evaluate_message(
            MessageIntent.GREETING,
            "Hello",
            config=MessagePolicyConfig(block_patterns=()),
        )


@pytest.mark.parametrize("pattern", ("", "["))
def test_invalid_policy_rules_fail_closed(pattern: str) -> None:
    with pytest.raises(PolicyUnavailable):
        evaluate_message(
            MessageIntent.GREETING,
            "Hello",
            config=MessagePolicyConfig(block_patterns=(pattern,)),
        )


@pytest.mark.parametrize("content", ("   ", "message is too long"))
def test_empty_or_oversized_messages_require_human_review(content: str) -> None:
    decision = evaluate_message(
        MessageIntent.GREETING,
        content,
        config=MessagePolicyConfig(max_content_length=5),
    )

    assert decision.allowed is False
    assert decision.code == "requires_human_review"
