"""Lightweight NLU that runs *before* the LLM on every turn.

Doing intent, sentiment, language and PII detection locally means:
  * routing and escalation decisions never depend on a network call,
  * analytics are populated even when the LLM is the mock provider,
  * personal data can be redacted before it ever leaves the process.

These are deliberately transparent, auditable classifiers - a real deployment
would swap the scorers for a fine-tuned model while keeping this interface.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.core.config import settings
from app.models.enums import Intent, Sentiment

# ---------------------------------------------------------------------------
# Intent classification - weighted keyword / phrase scoring
# ---------------------------------------------------------------------------
INTENT_PATTERNS: dict[Intent, list[tuple[str, float]]] = {
    Intent.HUMAN_HANDOFF: [
        (r"\b(human|real person|live agent|customer care executive|representative)\b", 3.0),
        (r"\b(talk|speak|connect|transfer)\b.{0,20}\b(someone|agent|human|person|manager)\b", 3.0),
        (r"\b(supervisor|manager|escalate)\b", 2.2),
    ],
    Intent.CANCEL_ORDER: [
        (r"\bcancel\b.{0,25}\b(order|item|purchase|booking)\b", 3.0),
        (r"\b(don'?t|do not) want (it|this|the order)\b", 2.0),
        (r"\bcancel my\b", 2.5),
    ],
    Intent.RETURN_REFUND: [
        (r"\b(return|refund|replace|exchange)\b", 2.6),
        (r"\b(damaged|defective|broken|faulty|torn|not working)\b", 2.2),
        (r"\b(wrong|different) (item|product|size|colour|color)\b", 2.4),
        (r"\b(money back|rma)\b", 2.4),
    ],
    Intent.TRACK_SHIPMENT: [
        (r"\b(track|tracking|awb|consignment)\b", 2.8),
        (r"\bwhere is my (order|parcel|package|delivery|shipment)\b", 3.0),
        (r"\b(courier|shipment|out for delivery|dispatched)\b", 2.0),
    ],
    Intent.DELIVERY_DELAY: [
        (r"\b(late|delay|delayed|still not|haven'?t received|not delivered|overdue)\b", 2.6),
        (r"\b(\d+\s*(days?|weeks?))\b.{0,25}\b(late|waiting|no update)\b", 2.4),
    ],
    Intent.ORDER_STATUS: [
        (r"\b(order status|status of my order|my order|order number|order id)\b", 2.6),
        (r"\bORD[- ]?\d{4,}\b", 3.0),
        (r"\b(what happened to|update on)\b.{0,20}\border\b", 2.2),
    ],
    Intent.STOCK_AVAILABILITY: [
        (r"\b(in stock|out of stock|available|availability|restock)\b", 2.6),
        (r"\bdo you (have|sell|stock)\b", 2.6),
    ],
    Intent.PRODUCT_RECOMMENDATION: [
        (r"\b(recommend|suggest|which one|best|better|compare|vs\.?)\b", 2.4),
        (r"\b(looking for|need something|help me (choose|pick|find))\b", 2.6),
    ],
    Intent.PRODUCT_INQUIRY: [
        (r"\b(specification|specs|warranty|material|dimensions|weight|feature|colour|color)\b", 2.0),
        (r"\b(how (does|do)|what is|tell me about)\b.{0,25}\b(product|item|model)\b", 2.0),
    ],
    Intent.PAYMENT_ISSUE: [
        (r"\b(payment|paid|charged|debited|transaction|upi|card|emi|cod)\b", 2.2),
        (r"\b(double charged|amount deducted|payment failed|not refunded)\b", 3.0),
    ],
    Intent.OFFERS_DISCOUNTS: [
        (r"\b(coupon|promo|discount|offer|sale|voucher|cashback|deal)\b", 2.4),
    ],
    Intent.ACCOUNT_HELP: [
        (r"\b(login|log in|sign ?in|password|otp|my account|profile|address book)\b", 2.2),
        (r"\b(loyalty|points|tier|membership|reward)\b", 2.0),
    ],
    Intent.STORE_INFO: [
        (r"\b(store|showroom|outlet|branch)\b.{0,20}\b(near|nearby|address|timing|open)\b", 2.8),
        (r"\b(opening hours|store timing|pickup|click and collect)\b", 2.4),
    ],
    Intent.COMPLAINT: [
        (r"\b(complaint|complain|worst|terrible|pathetic|unacceptable|disgusting)\b", 2.8),
        (r"\b(third time|again and again|no one (responded|replied|called))\b", 2.6),
        (r"\b(consumer (court|forum)|legal action|social media)\b", 3.0),
    ],
    Intent.SMALL_TALK: [
        (r"^\s*(hi|hey|hello|namaste|good (morning|afternoon|evening))\b", 2.0),
        (r"\b(thank you|thanks|bye|goodbye|how are you)\b", 1.6),
    ],
}


@dataclass(slots=True)
class IntentResult:
    intent: Intent
    confidence: float
    scores: dict[str, float]


def classify_intent(text: str) -> IntentResult:
    lowered = (text or "").lower().strip()
    if not lowered:
        return IntentResult(Intent.UNKNOWN, 0.0, {})

    scores: dict[Intent, float] = {}
    for intent, patterns in INTENT_PATTERNS.items():
        total = 0.0
        for pattern, weight in patterns:
            if re.search(pattern, lowered, re.I):
                total += weight
        if total:
            scores[intent] = total

    if not scores:
        return IntentResult(Intent.UNKNOWN, 0.25, {})

    ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
    best, best_score = ranked[0]
    runner_up = ranked[1][1] if len(ranked) > 1 else 0.0

    # Confidence blends absolute evidence with the margin over the runner-up.
    saturation = min(1.0, best_score / 5.0)
    margin = (best_score - runner_up) / best_score if best_score else 0.0
    confidence = round(min(0.98, 0.45 * saturation + 0.55 * (0.4 + 0.6 * margin)), 3)

    return IntentResult(best, confidence, {k.value: round(v, 2) for k, v in ranked[:5]})


# ---------------------------------------------------------------------------
# Sentiment - lexicon with negation and intensifier handling
# ---------------------------------------------------------------------------
POSITIVE_LEXICON = {
    "thanks": 1.0, "thank": 1.0, "great": 1.2, "good": 0.8, "excellent": 1.6,
    "awesome": 1.5, "love": 1.5, "perfect": 1.5, "happy": 1.2, "helpful": 1.2,
    "quick": 0.7, "fast": 0.7, "resolved": 1.0, "appreciate": 1.2, "amazing": 1.5,
    "satisfied": 1.2, "wonderful": 1.4, "nice": 0.8, "brilliant": 1.4,
}
NEGATIVE_LEXICON = {
    "bad": -1.0, "worst": -2.0, "terrible": -1.8, "awful": -1.8, "hate": -1.8,
    "angry": -1.6, "furious": -2.0, "annoyed": -1.2, "frustrated": -1.5,
    "disappointed": -1.4, "useless": -1.6, "pathetic": -1.8, "rubbish": -1.5,
    "unacceptable": -1.8, "poor": -1.1, "slow": -0.8, "late": -0.9, "delay": -0.9,
    "delayed": -1.0, "broken": -1.2, "damaged": -1.2, "defective": -1.3,
    "cheated": -1.9, "scam": -2.0, "fraud": -2.0, "never": -0.7, "refuse": -1.2,
    "complaint": -1.2, "waiting": -0.8, "ridiculous": -1.6, "disgusting": -1.9,
    "harassment": -2.0, "worse": -1.4, "failed": -1.1, "stuck": -0.9,
}
INTENSIFIERS = {"very": 1.5, "extremely": 1.8, "really": 1.4, "so": 1.3,
                "totally": 1.5, "absolutely": 1.7, "completely": 1.6, "highly": 1.4}
NEGATIONS = {"not", "no", "never", "n't", "dont", "don't", "didn't", "isn't", "wasn't"}


@dataclass(slots=True)
class SentimentResult:
    label: Sentiment
    score: float          # -1.0 .. +1.0
    magnitude: float


def analyze_sentiment(text: str) -> SentimentResult:
    tokens = re.findall(r"[a-z']+", (text or "").lower())
    if not tokens:
        return SentimentResult(Sentiment.NEUTRAL, 0.0, 0.0)

    total = 0.0
    magnitude = 0.0
    for i, tok in enumerate(tokens):
        base = POSITIVE_LEXICON.get(tok, 0.0) or NEGATIVE_LEXICON.get(tok, 0.0)
        if base == 0.0:
            continue
        weight = 1.0
        window = tokens[max(0, i - 2): i]
        for prev in window:
            if prev in INTENSIFIERS:
                weight *= INTENSIFIERS[prev]
            if prev in NEGATIONS:
                weight *= -0.85
        value = base * weight
        total += value
        magnitude += abs(value)

    # Non-lexical anger signals
    if re.search(r"[A-Z]{5,}", text or ""):          # SHOUTING
        total -= 0.5
        magnitude += 0.5
    exclamations = (text or "").count("!")
    if exclamations >= 2:
        total -= 0.3 * min(exclamations, 4)
        magnitude += 0.3

    # Normalise by a floor plus a sub-linear length term, so a long message
    # doesn't score "very negative" just for containing more words.
    denominator = max(6.0, 2.0 * len(tokens) ** 0.5)
    score = max(-1.0, min(1.0, total / denominator))

    if score <= -0.55:
        label = Sentiment.VERY_NEGATIVE
    elif score <= -0.15:
        label = Sentiment.NEGATIVE
    elif score < 0.15:
        label = Sentiment.NEUTRAL
    elif score < 0.55:
        label = Sentiment.POSITIVE
    else:
        label = Sentiment.VERY_POSITIVE

    return SentimentResult(label, round(score, 3), round(magnitude, 3))


# ---------------------------------------------------------------------------
# Language detection (script + stop-word heuristics for the Indian retail mix)
# ---------------------------------------------------------------------------
LANGUAGE_MARKERS: dict[str, set[str]] = {
    "hi": {"hai", "nahi", "kya", "mera", "meri", "kab", "kaise", "aap", "order",
           "paisa", "wapas", "chahiye", "kyun", "bhai", "karo", "kar", "raha"},
    "es": {"hola", "gracias", "pedido", "donde", "esta", "quiero", "devolver"},
    "fr": {"bonjour", "merci", "commande", "livraison", "retour", "sil"},
}


def detect_language(text: str) -> str:
    if not text:
        return "en"
    if re.search(r"[ऀ-ॿ]", text):     # Devanagari
        return "hi"
    if re.search(r"[஀-௿]", text):     # Tamil
        return "ta"
    if re.search(r"[ఀ-౿]", text):     # Telugu
        return "te"
    if re.search(r"[؀-ۿ]", text):     # Arabic / Urdu
        return "ur"

    words = set(re.findall(r"[a-z']+", text.lower()))
    for lang, markers in LANGUAGE_MARKERS.items():
        if len(words & markers) >= 2:
            return lang
    return "en"


# ---------------------------------------------------------------------------
# PII redaction
# ---------------------------------------------------------------------------
PII_RULES: list[tuple[str, str]] = [
    (r"\b[\w.+-]+@[\w-]+\.[\w.]{2,}\b", "[EMAIL]"),
    (r"\b(?:\d[ -]?){13,16}\b", "[CARD]"),
    (r"\b\d{4}\s?\d{4}\s?\d{4}\b", "[NATIONAL_ID]"),
    (r"\b(?:\+91[\s-]?|0)?[6-9]\d{9}\b", "[PHONE]"),
    (r"\b[A-Z]{5}\d{4}[A-Z]\b", "[TAX_ID]"),
    (r"\b(?:cvv|otp|pin)\s*[:=]?\s*\d{3,6}\b", "[SECRET]"),
]


@dataclass(slots=True)
class RedactionResult:
    text: str
    was_redacted: bool
    kinds: list[str]


def redact_pii(text: str) -> RedactionResult:
    """Mask sensitive identifiers before storage / model calls.

    Order numbers (ORD-xxxxx) and tracking IDs are intentionally preserved -
    the agent needs them, and they are not personal data on their own.
    """
    if not settings.ENABLE_PII_REDACTION or not text:
        return RedactionResult(text, False, [])

    redacted = text
    kinds: list[str] = []
    for pattern, placeholder in PII_RULES:
        redacted, count = re.subn(pattern, placeholder, redacted, flags=re.I)
        if count:
            kinds.append(placeholder.strip("[]").lower())
    return RedactionResult(redacted, bool(kinds), kinds)


# ---------------------------------------------------------------------------
# Combined pass
# ---------------------------------------------------------------------------
@dataclass(slots=True)
class NLUResult:
    text: str
    redacted_text: str
    was_redacted: bool
    pii_kinds: list[str]
    intent: Intent
    intent_confidence: float
    intent_scores: dict[str, float]
    sentiment: Sentiment
    sentiment_score: float
    language: str

    @property
    def is_frustrated(self) -> bool:
        return self.sentiment_score <= settings.ESCALATION_SENTIMENT_THRESHOLD


def analyze(text: str) -> NLUResult:
    intent = classify_intent(text)
    sentiment = analyze_sentiment(text)
    redaction = redact_pii(text)
    return NLUResult(
        text=text,
        redacted_text=redaction.text,
        was_redacted=redaction.was_redacted,
        pii_kinds=redaction.kinds,
        intent=intent.intent,
        intent_confidence=intent.confidence,
        intent_scores=intent.scores,
        sentiment=sentiment.label,
        sentiment_score=sentiment.score,
        language=detect_language(text),
    )


# ---------------------------------------------------------------------------
# Suggested quick replies shown as chips in the UI
# ---------------------------------------------------------------------------
SUGGESTIONS: dict[Intent, list[str]] = {
    Intent.ORDER_STATUS: ["Track this shipment", "Change delivery address", "Cancel this order"],
    Intent.TRACK_SHIPMENT: ["It's late - help", "Change delivery date", "Talk to an agent"],
    Intent.DELIVERY_DELAY: ["Cancel and refund", "Raise a complaint", "Talk to an agent"],
    Intent.CANCEL_ORDER: ["Yes, cancel it", "What's the refund timeline?", "Keep the order"],
    Intent.RETURN_REFUND: ["Start a return", "What's the return policy?", "Refund status"],
    Intent.PRODUCT_INQUIRY: ["Check availability", "Show similar products", "Warranty details"],
    Intent.PRODUCT_RECOMMENDATION: ["Show cheaper options", "Best rated only", "Compare top 2"],
    Intent.STOCK_AVAILABILITY: ["Notify me when in stock", "Show alternatives", "Find in a store"],
    Intent.PAYMENT_ISSUE: ["Refund status", "Retry payment", "Talk to an agent"],
    Intent.OFFERS_DISCOUNTS: ["Current offers", "Apply my coupon", "Loyalty points balance"],
    Intent.ACCOUNT_HELP: ["Reset password", "Update address", "My loyalty tier"],
    Intent.STORE_INFO: ["Store timings", "Book click & collect", "Directions"],
    Intent.COMPLAINT: ["Escalate to a manager", "Track my complaint", "Request a callback"],
    Intent.HUMAN_HANDOFF: ["Yes, connect me", "Call me back instead", "Continue with the assistant"],
}
DEFAULT_SUGGESTIONS = ["Track my order", "Start a return", "Talk to an agent"]


def suggested_replies(intent: Intent) -> list[str]:
    return SUGGESTIONS.get(intent, DEFAULT_SUGGESTIONS)
