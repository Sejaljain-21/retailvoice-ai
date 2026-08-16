"""Deterministic guardrails that run around the model, not inside it.

An LLM can be persuaded; these checks cannot. They run *before* the model sees a
turn (input guardrails) and *after* it produces one (output guardrails), plus a
rules-based escalation decision that does not depend on the model choosing to
call the escalation tool.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.core.config import settings
from app.models.enums import EscalationReason, Intent, Sentiment
from app.services.nlu import NLUResult

# ---------------------------------------------------------------------------
# Input guardrails
# ---------------------------------------------------------------------------
PROMPT_INJECTION_PATTERNS = [
    r"ignore (all |your |the )?(previous|prior|above) instructions",
    r"disregard (your|the|all) (rules|instructions|guidelines)",
    r"you are now (a|an|in) ",
    r"system prompt|reveal your (prompt|instructions)",
    r"developer mode|jailbreak|DAN mode",
    r"print (your|the) (instructions|system message)",
]

# Topics the agent must never handle autonomously.
HARD_ESCALATION_PATTERNS = [
    (r"\b(lawyer|legal action|consumer (court|forum)|sue|lawsuit|police|fir)\b",
     "legal threat"),
    (r"\b(fraud|unauthorised transaction|unauthorized transaction|stolen card|hacked)\b",
     "suspected fraud"),
    (r"\b(injur\w+|burn|shock|fire|exploded|hospital|allerg\w+|poison)\b",
     "product safety / injury"),
    (r"\b(self ?harm|suicide|kill myself)\b", "welfare concern"),
    (r"\b(media|press|twitter|journalist|viral)\b.{0,30}\b(complain|expose|post)\b",
     "reputational risk"),
]

CREDENTIAL_REQUEST_PATTERNS = [
    r"\b(cvv|card number|otp|one time password|upi pin|password|net ?banking password)\b",
]


@dataclass(slots=True)
class GuardrailVerdict:
    allowed: bool = True
    blocked_reason: str | None = None
    forced_escalation: EscalationReason | None = None
    escalation_note: str = ""
    warnings: list[str] | None = None
    sanitized_text: str | None = None


def check_input(text: str, nlu: NLUResult) -> GuardrailVerdict:
    warnings: list[str] = []
    lowered = (text or "").lower()

    for pattern in PROMPT_INJECTION_PATTERNS:
        if re.search(pattern, lowered, re.I):
            warnings.append("prompt_injection_attempt")
            break

    for pattern, label in HARD_ESCALATION_PATTERNS:
        if re.search(pattern, lowered, re.I):
            return GuardrailVerdict(
                allowed=True,
                forced_escalation=EscalationReason.POLICY_LIMIT,
                escalation_note=(
                    f"Automatic escalation: {label} detected in the customer's message. "
                    "This category must be handled by a trained human agent."
                ),
                warnings=warnings + [label],
            )

    for pattern in CREDENTIAL_REQUEST_PATTERNS:
        if re.search(pattern, lowered, re.I):
            warnings.append("credential_mentioned")

    return GuardrailVerdict(allowed=True, warnings=warnings or None)


# ---------------------------------------------------------------------------
# Output guardrails
# ---------------------------------------------------------------------------
LEAK_PATTERNS = [
    (r"\b(sk-ant-|sk-[A-Za-z0-9]{20,})", "[REDACTED_KEY]"),
    (r"\bBearer\s+[A-Za-z0-9._\-]{20,}", "[REDACTED_TOKEN]"),
    (r"postgres(ql)?://[^\s]+", "[REDACTED_DSN]"),
]

BANNED_PHRASES = [
    "as an ai language model",
    "i am just an ai",
    "my system prompt",
    "my instructions say",
]


def check_output(text: str) -> GuardrailVerdict:
    warnings: list[str] = []
    cleaned = text or ""

    for pattern, replacement in LEAK_PATTERNS:
        cleaned, count = re.subn(pattern, replacement, cleaned)
        if count:
            warnings.append("secret_redacted")

    lowered = cleaned.lower()
    for phrase in BANNED_PHRASES:
        if phrase in lowered:
            warnings.append("meta_disclosure")
            break

    # An empty model turn is a failure, not an answer.
    if not cleaned.strip():
        return GuardrailVerdict(
            allowed=False,
            blocked_reason="empty_response",
            warnings=warnings or None,
        )

    return GuardrailVerdict(
        allowed=True, sanitized_text=cleaned, warnings=warnings or None
    )


# ---------------------------------------------------------------------------
# Escalation decision
# ---------------------------------------------------------------------------
@dataclass(slots=True)
class EscalationDecision:
    should_escalate: bool
    reason: EscalationReason | None = None
    note: str = ""


def should_escalate(
    *,
    nlu: NLUResult,
    turn_count: int,
    consecutive_low_confidence: int = 0,
    tool_errors: int = 0,
    customer_tier: str = "standard",
    already_escalated: bool = False,
    guardrail: GuardrailVerdict | None = None,
) -> EscalationDecision:
    """Rules that can escalate even if the model never asks to."""
    if already_escalated:
        return EscalationDecision(False)

    if guardrail and guardrail.forced_escalation:
        return EscalationDecision(True, guardrail.forced_escalation, guardrail.escalation_note)

    if nlu.intent == Intent.HUMAN_HANDOFF and nlu.intent_confidence >= 0.5:
        return EscalationDecision(
            True, EscalationReason.CUSTOMER_REQUEST,
            "The customer explicitly asked to speak to a human.",
        )

    if nlu.sentiment_score <= settings.ESCALATION_SENTIMENT_THRESHOLD:
        return EscalationDecision(
            True, EscalationReason.NEGATIVE_SENTIMENT,
            f"Sentiment fell to {nlu.sentiment_score:+.2f} "
            f"({nlu.sentiment.value}) - handing to a human before it gets worse.",
        )

    if tool_errors >= 2:
        return EscalationDecision(
            True, EscalationReason.TOOL_ERROR,
            "Two or more backend tools failed during this conversation.",
        )

    if consecutive_low_confidence >= 3:
        return EscalationDecision(
            True, EscalationReason.LOW_CONFIDENCE,
            "The assistant could not confidently classify three consecutive turns.",
        )

    if turn_count >= settings.ESCALATION_MAX_TURNS_WITHOUT_RESOLUTION and nlu.sentiment_score < 0:
        return EscalationDecision(
            True, EscalationReason.REPEATED_FAILURE,
            f"{turn_count} turns without resolution and sentiment is negative.",
        )

    if (
        customer_tier in ("gold", "platinum")
        and nlu.sentiment in (Sentiment.NEGATIVE, Sentiment.VERY_NEGATIVE)
        and turn_count >= 4
    ):
        return EscalationDecision(
            True, EscalationReason.HIGH_VALUE_CUSTOMER,
            f"{customer_tier.title()}-tier customer is unhappy after {turn_count} turns.",
        )

    return EscalationDecision(False)


def refund_needs_approval(amount: float) -> bool:
    return amount > settings.ESCALATION_REFUND_AMOUNT_LIMIT


HANDOFF_MESSAGE = (
    "I'm connecting you with one of my human colleagues now - they'll have this whole "
    "conversation in front of them, so you won't have to repeat anything. "
    "Your reference number is **{ticket_number}**."
)
