"""Ticket queue for the human agent console."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Query, status
from sqlalchemy import desc, func, select

from app.api.deps import CurrentUser, DbSession, Pagination, StaffUser
from app.core.exceptions import NotFoundError, PermissionError_
from app.models.enums import TicketStatus, UserRole
from app.models.support import Ticket
from app.schemas.common import Page
from app.schemas.support import CreateTicketRequest, TicketOut, UpdateTicketRequest
from app.services import tickets_service

router = APIRouter()

PRIORITY_RANK = {"urgent": 0, "high": 1, "medium": 2, "low": 3}


@router.get("", response_model=Page[TicketOut])
async def list_tickets(
    user: CurrentUser,
    db: DbSession,
    page: Pagination,
    status_filter: str | None = Query(None, alias="status"),
    priority: str | None = None,
    assigned_to_me: bool = False,
    q: str | None = Query(None, description="Search subject and ticket number"),
) -> Page[TicketOut]:
    is_staff = user.role in (UserRole.AGENT, UserRole.SUPERVISOR, UserRole.ADMIN)

    stmt = select(Ticket)
    count_stmt = select(func.count(Ticket.id))
    filters = []

    if not is_staff:
        filters.append(Ticket.customer_id == user.id)
    elif assigned_to_me:
        filters.append(Ticket.assigned_agent_id == user.id)
    if status_filter:
        filters.append(Ticket.status == status_filter)
    if priority:
        filters.append(Ticket.priority == priority)
    if q:
        like = f"%{q.strip()}%"
        filters.append(Ticket.subject.ilike(like) | Ticket.ticket_number.ilike(like))

    for f in filters:
        stmt = stmt.where(f)
        count_stmt = count_stmt.where(f)

    rows = (
        await db.execute(
            stmt.order_by(desc(Ticket.created_at)).limit(page.page_size).offset(page.offset)
        )
    ).scalars().all()
    total = int((await db.execute(count_stmt)).scalar_one())

    # Urgent work first, then newest.
    ordered = sorted(rows, key=lambda t: (PRIORITY_RANK.get(t.priority, 9), -t.created_at.timestamp()))

    return Page[TicketOut](
        items=[TicketOut.model_validate(t) for t in ordered],
        total=total, page=page.page, page_size=page.page_size,
    )


@router.post("", response_model=TicketOut, status_code=status.HTTP_201_CREATED)
async def create_ticket(
    payload: CreateTicketRequest, user: CurrentUser, db: DbSession
) -> TicketOut:
    ticket = await tickets_service.create_ticket(
        db,
        subject=payload.subject,
        description=payload.description,
        category=payload.category,
        priority=payload.priority,
        customer_id=user.id,
        conversation_id=payload.conversation_id,
        order_id=payload.order_id,
        tags=payload.tags,
    )
    return TicketOut.model_validate(ticket)


@router.get("/stats")
async def ticket_stats(db: DbSession, staff: StaffUser) -> dict:
    async def count(**where) -> int:
        stmt = select(func.count(Ticket.id))
        for column, value in where.items():
            stmt = stmt.where(getattr(Ticket, column) == value)
        return int((await db.execute(stmt)).scalar_one())

    now = datetime.now(timezone.utc)
    breaching = (
        await db.execute(
            select(func.count(Ticket.id)).where(
                Ticket.sla_due_at < now,
                Ticket.status.in_([TicketStatus.OPEN, TicketStatus.IN_PROGRESS]),
            )
        )
    ).scalar_one()

    return {
        "open": await count(status=TicketStatus.OPEN),
        "in_progress": await count(status=TicketStatus.IN_PROGRESS),
        "waiting_customer": await count(status=TicketStatus.WAITING_CUSTOMER),
        "resolved": await count(status=TicketStatus.RESOLVED),
        "urgent": await count(priority="urgent"),
        "ai_created": int(
            (await db.execute(
                select(func.count(Ticket.id)).where(Ticket.created_by_agent.is_(True))
            )).scalar_one()
        ),
        "sla_breaching": int(breaching),
        "queue_depth": await tickets_service.queue_depth(db),
    }


@router.get("/{ticket_id}", response_model=TicketOut)
async def get_ticket(ticket_id: str, user: CurrentUser, db: DbSession) -> TicketOut:
    ticket = (
        await db.execute(
            select(Ticket).where(
                (Ticket.id == ticket_id) | (Ticket.ticket_number == ticket_id)
            )
        )
    ).scalars().first()
    if not ticket:
        raise NotFoundError("Ticket not found.")

    is_staff = user.role in (UserRole.AGENT, UserRole.SUPERVISOR, UserRole.ADMIN)
    if not is_staff and ticket.customer_id != user.id:
        raise PermissionError_("You can only view your own tickets.")
    return TicketOut.model_validate(ticket)


@router.patch("/{ticket_id}", response_model=TicketOut)
async def update_ticket(
    ticket_id: str, payload: UpdateTicketRequest, staff: StaffUser, db: DbSession
) -> TicketOut:
    ticket = (
        await db.execute(
            select(Ticket).where(
                (Ticket.id == ticket_id) | (Ticket.ticket_number == ticket_id)
            )
        )
    ).scalars().first()
    if not ticket:
        raise NotFoundError("Ticket not found.")

    if payload.status:
        ticket.status = payload.status
        if payload.status in (TicketStatus.RESOLVED, TicketStatus.CLOSED):
            ticket.resolved_at = datetime.now(timezone.utc)
    if payload.priority:
        ticket.priority = payload.priority
    if payload.assigned_agent_id is not None:
        ticket.assigned_agent_id = payload.assigned_agent_id or None
    if payload.resolution_note is not None:
        ticket.resolution_note = payload.resolution_note
    if payload.tags is not None:
        ticket.tags = payload.tags
    if ticket.first_response_at is None:
        ticket.first_response_at = datetime.now(timezone.utc)

    await db.flush()
    return TicketOut.model_validate(ticket)


@router.post("/{ticket_id}/claim", response_model=TicketOut)
async def claim_ticket(ticket_id: str, staff: StaffUser, db: DbSession) -> TicketOut:
    ticket = (
        await db.execute(
            select(Ticket).where(
                (Ticket.id == ticket_id) | (Ticket.ticket_number == ticket_id)
            )
        )
    ).scalars().first()
    if not ticket:
        raise NotFoundError("Ticket not found.")

    ticket.assigned_agent_id = staff.id
    if ticket.status == TicketStatus.OPEN:
        ticket.status = TicketStatus.IN_PROGRESS
    if ticket.first_response_at is None:
        ticket.first_response_at = datetime.now(timezone.utc)
    await db.flush()
    return TicketOut.model_validate(ticket)
