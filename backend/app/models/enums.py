"""Domain enumerations.

Stored as plain strings in the database so that adding a value never needs a
schema migration, but exposed as `StrEnum` for type-safety in Python.
"""

from __future__ import annotations

try:
    from enum import StrEnum
except ImportError:
    from enum import Enum

    class StrEnum(str, Enum):
        def __str__(self) -> str:
            return str(self.value)


class UserRole(StrEnum):
    CUSTOMER = "customer"
    AGENT = "agent"       # human support agent
    SUPERVISOR = "supervisor"
    ADMIN = "admin"


class CustomerTier(StrEnum):
    STANDARD = "standard"
    SILVER = "silver"
    GOLD = "gold"
    PLATINUM = "platinum"


class OrderStatus(StrEnum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    PACKED = "packed"
    SHIPPED = "shipped"
    OUT_FOR_DELIVERY = "out_for_delivery"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"
    RETURNED = "returned"


class PaymentStatus(StrEnum):
    PENDING = "pending"
    PAID = "paid"
    FAILED = "failed"
    REFUNDED = "refunded"
    PARTIALLY_REFUNDED = "partially_refunded"


class ShipmentStatus(StrEnum):
    LABEL_CREATED = "label_created"
    IN_TRANSIT = "in_transit"
    OUT_FOR_DELIVERY = "out_for_delivery"
    DELIVERED = "delivered"
    EXCEPTION = "exception"
    RETURNING = "returning"


class ReturnStatus(StrEnum):
    REQUESTED = "requested"
    APPROVED = "approved"
    REJECTED = "rejected"
    PICKED_UP = "picked_up"
    REFUNDED = "refunded"


class ChannelType(StrEnum):
    WEB_CHAT = "web_chat"
    VOICE = "voice"
    EMAIL = "email"
    WHATSAPP = "whatsapp"
    PHONE = "phone"


class ConversationStatus(StrEnum):
    ACTIVE = "active"
    RESOLVED = "resolved"
    ESCALATED = "escalated"
    ABANDONED = "abandoned"


class MessageRole(StrEnum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"
    TOOL = "tool"
    HUMAN_AGENT = "human_agent"


class TicketStatus(StrEnum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    WAITING_CUSTOMER = "waiting_customer"
    RESOLVED = "resolved"
    CLOSED = "closed"


class TicketPriority(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


class Intent(StrEnum):
    ORDER_STATUS = "order_status"
    TRACK_SHIPMENT = "track_shipment"
    CANCEL_ORDER = "cancel_order"
    RETURN_REFUND = "return_refund"
    PRODUCT_INQUIRY = "product_inquiry"
    PRODUCT_RECOMMENDATION = "product_recommendation"
    STOCK_AVAILABILITY = "stock_availability"
    PAYMENT_ISSUE = "payment_issue"
    DELIVERY_DELAY = "delivery_delay"
    ACCOUNT_HELP = "account_help"
    OFFERS_DISCOUNTS = "offers_discounts"
    STORE_INFO = "store_info"
    COMPLAINT = "complaint"
    SMALL_TALK = "small_talk"
    HUMAN_HANDOFF = "human_handoff"
    UNKNOWN = "unknown"


class Sentiment(StrEnum):
    VERY_NEGATIVE = "very_negative"
    NEGATIVE = "negative"
    NEUTRAL = "neutral"
    POSITIVE = "positive"
    VERY_POSITIVE = "very_positive"


class EscalationReason(StrEnum):
    CUSTOMER_REQUEST = "customer_request"
    NEGATIVE_SENTIMENT = "negative_sentiment"
    LOW_CONFIDENCE = "low_confidence"
    POLICY_LIMIT = "policy_limit"
    REPEATED_FAILURE = "repeated_failure"
    HIGH_VALUE_CUSTOMER = "high_value_customer"
    TOOL_ERROR = "tool_error"
