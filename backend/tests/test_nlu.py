"""Unit tests for the local NLU layer (intent, sentiment, language, PII)."""

from __future__ import annotations

import pytest

from app.models.enums import Intent, Sentiment
from app.services import nlu


@pytest.mark.parametrize(
    "text,expected",
    [
        ("Where is my order? It should have arrived yesterday.", Intent.TRACK_SHIPMENT),
        ("I want to cancel my order please", Intent.CANCEL_ORDER),
        ("The shoes are damaged, I want a refund", Intent.RETURN_REFUND),
        ("Do you have the wireless headphones in stock?", Intent.STOCK_AVAILABILITY),
        ("Can I talk to a real person?", Intent.HUMAN_HANDOFF),
        ("I was charged twice on my card", Intent.PAYMENT_ISSUE),
        ("Any coupon code for a 3000 rupee order?", Intent.OFFERS_DISCOUNTS),
        ("What time does your Koramangala store open?", Intent.STORE_INFO),
        ("hello", Intent.SMALL_TALK),
    ],
)
def test_intent_classification(text: str, expected: Intent) -> None:
    result = nlu.classify_intent(text)
    assert result.intent == expected
    assert 0.0 < result.confidence <= 1.0


def test_unknown_intent_is_low_confidence() -> None:
    result = nlu.classify_intent("the quick brown fox jumps")
    assert result.intent == Intent.UNKNOWN
    assert result.confidence < 0.5


@pytest.mark.parametrize(
    "text,expected",
    [
        ("This is absolutely terrible, worst service ever!!", Sentiment.VERY_NEGATIVE),
        ("I am a bit disappointed with the delay", Sentiment.NEGATIVE),
        ("What is the status of my order", Sentiment.NEUTRAL),
        ("Thanks, that was really helpful", Sentiment.POSITIVE),
    ],
)
def test_sentiment(text: str, expected: Sentiment) -> None:
    assert nlu.analyze_sentiment(text).label == expected


def test_sentiment_handles_negation() -> None:
    positive = nlu.analyze_sentiment("this is good").score
    negated = nlu.analyze_sentiment("this is not good").score
    assert negated < positive


def test_language_detection() -> None:
    assert nlu.detect_language("Where is my order?") == "en"
    assert nlu.detect_language("मेरा ऑर्डर कहाँ है") == "hi"
    assert nlu.detect_language("mera order kab aayega bhai kya kar raha hai") == "hi"


def test_pii_redaction_masks_contact_details() -> None:
    result = nlu.redact_pii(
        "Email me at aarav.sharma@example.com or call 9845012345, card 4111111111111111"
    )
    assert result.was_redacted
    assert "aarav.sharma@example.com" not in result.text
    assert "9845012345" not in result.text
    assert "4111111111111111" not in result.text
    assert "[EMAIL]" in result.text


def test_pii_redaction_preserves_order_numbers() -> None:
    result = nlu.redact_pii("My order ORD-2508123456 has not arrived")
    assert "ORD-2508123456" in result.text


def test_combined_analysis() -> None:
    result = nlu.analyze("My order is 5 days late and this is unacceptable!")
    assert result.intent in (Intent.DELIVERY_DELAY, Intent.COMPLAINT, Intent.TRACK_SHIPMENT)
    assert result.sentiment_score < 0
    assert result.language == "en"


def test_suggested_replies_always_returns_chips() -> None:
    for intent in Intent:
        assert len(nlu.suggested_replies(intent)) >= 1
