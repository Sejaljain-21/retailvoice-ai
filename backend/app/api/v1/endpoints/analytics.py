"""Operations analytics for the supervisor dashboard."""

from __future__ import annotations

from fastapi import APIRouter, Query

from app.api.deps import DbSession, StaffUser
from app.services import analytics_service

router = APIRouter()


@router.get("/dashboard")
async def dashboard(
    db: DbSession,
    staff: StaffUser,
    days: int = Query(30, ge=1, le=365),
) -> dict:
    """Everything the analytics screen needs, in one round-trip."""
    return await analytics_service.dashboard(db, days)


@router.get("/kpis")
async def kpis(db: DbSession, staff: StaffUser, days: int = Query(30, ge=1, le=365)) -> dict:
    return await analytics_service.kpi_summary(db, days)


@router.get("/intents")
async def intents(db: DbSession, staff: StaffUser) -> list[dict]:
    return await analytics_service.intent_breakdown(db)


@router.get("/channels")
async def channels(db: DbSession, staff: StaffUser) -> list[dict]:
    return await analytics_service.channel_breakdown(db)


@router.get("/timeseries")
async def timeseries(db: DbSession, staff: StaffUser, days: int = Query(14, ge=1, le=90)) -> list[dict]:
    return await analytics_service.timeseries(db, days)


@router.get("/tools")
async def tools(db: DbSession, staff: StaffUser) -> list[dict]:
    return await analytics_service.tool_usage(db)


@router.get("/sentiment")
async def sentiment(db: DbSession, staff: StaffUser) -> list[dict]:
    return await analytics_service.sentiment_distribution(db)
