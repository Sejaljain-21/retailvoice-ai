"""Import every model so `Base.metadata` is complete before `create_all`."""

from app.db.base import Base
from app.models.catalog import Category, Product, StoreLocation
from app.models.knowledge import KBChunk, KBDocument
from app.models.order import Order, OrderItem, ReturnRequest, Shipment
from app.models.support import (
    Conversation,
    Feedback,
    Message,
    Ticket,
    ToolCallLog,
)
from app.models.user import CustomerProfile, User

__all__ = [
    "Base",
    "Category",
    "Product",
    "StoreLocation",
    "KBChunk",
    "KBDocument",
    "Order",
    "OrderItem",
    "ReturnRequest",
    "Shipment",
    "Conversation",
    "Feedback",
    "Message",
    "Ticket",
    "ToolCallLog",
    "CustomerProfile",
    "User",
]
