"""Mounts every v1 endpoint module."""

from fastapi import APIRouter

from app.api.v1.endpoints import (
    analytics,
    auth,
    catalog,
    chat,
    health,
    knowledge,
    orders,
    tickets,
    voice,
)

api_router = APIRouter()

api_router.include_router(health.router, tags=["system"])
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(catalog.router, prefix="/catalog", tags=["catalog"])
api_router.include_router(orders.router, prefix="/orders", tags=["orders"])
api_router.include_router(chat.router, prefix="/chat", tags=["chat & conversations"])
api_router.include_router(voice.router, prefix="/voice", tags=["voice"])
api_router.include_router(tickets.router, prefix="/tickets", tags=["tickets"])
api_router.include_router(knowledge.router, prefix="/knowledge", tags=["knowledge base"])
api_router.include_router(analytics.router, prefix="/analytics", tags=["analytics"])
