"""Text chat with the AI support agent, plus conversation management."""

from __future__ import annotations

from fastapi import APIRouter, Query, status
from sqlalchemy import desc, func, select

from app.agent import get_or_create_conversation, run_turn
from app.agent.orchestrator import close_conversation
from app.api.deps import CurrentUser, DbSession, OptionalUser, Pagination, StaffUser
from app.core.exceptions import NotFoundError, PermissionError_
from app.models.enums import EscalationReason, MessageRole, UserRole
from app.models.support import Conversation, Feedback, Message
from app.schemas.common import Msg, Page
from app.schemas.support import (
    AgentReply,
    ChatRequest,
    Citation,
    ConversationDetail,
    ConversationOut,
    CreateConversationRequest,
    FeedbackOut,
    FeedbackRequest,
    HandoffRequest,
    MessageOut,
    ToolTrace,
)
from app.services import tickets_service

router = APIRouter()


def _to_reply(turn) -> AgentReply:
    return AgentReply(
        conversation_id=turn.conversation_id,
        message_id=turn.message_id,
        reply=turn.reply,
        intent=turn.intent,
        intent_confidence=turn.intent_confidence,
        sentiment=turn.sentiment,
        sentiment_score=turn.sentiment_score,
        citations=[
            Citation(
                document_id=c["document_id"], title=c["title"],
                snippet=c["snippet"][:400], score=c["score"], slug=c.get("slug"),
            )
            for c in turn.citations
        ],
        tool_trace=[
            ToolTrace(
                tool=t["tool"], arguments=t["arguments"], result=t["result"],
                success=t["success"], duration_ms=t["duration_ms"], error=t.get("error"),
            )
            for t in turn.tool_trace
        ],
        escalated=turn.escalated,
        escalation_reason=turn.escalation_reason,
        suggested_replies=turn.suggested_replies,
        handoff_ticket_number=turn.handoff_ticket_number,
        latency_ms=turn.latency_ms,
        model=turn.model,
        tokens_in=turn.tokens_in,
        tokens_out=turn.tokens_out,
    )


def _assert_can_view(user, conversation: Conversation) -> None:
    if user is None:
        return
    is_staff = user.role in (UserRole.AGENT, UserRole.SUPERVISOR, UserRole.ADMIN)
    if not is_staff and conversation.customer_id not in (None, user.id):
        raise PermissionError_("You can only view your own conversations.")


# ---------------------------------------------------------------------------
# Chat
# ---------------------------------------------------------------------------
@router.post("/message", response_model=AgentReply)
async def send_message(payload: ChatRequest, db: DbSession, user: OptionalUser) -> AgentReply:
    """Send one customer message and get the agent's grounded reply.

    Works signed-in or anonymous. Creates the conversation on the first call.
    """
    conversation = await get_or_create_conversation(
        db,
        conversation_id=payload.conversation_id,
        user=user,
        channel=payload.channel,
        language=payload.language,
        anonymous_key=payload.anonymous_key,
    )
    _assert_can_view(user, conversation)

    turn = await run_turn(
        db,
        conversation=conversation,
        user=user,
        text=payload.message,
        voice_mode=payload.voice_mode,
    )
    return _to_reply(turn)


# ---------------------------------------------------------------------------
# Conversations
# ---------------------------------------------------------------------------
@router.post("/conversations", response_model=ConversationOut,
             status_code=status.HTTP_201_CREATED)
async def create_conversation(
    payload: CreateConversationRequest, db: DbSession, user: OptionalUser
) -> ConversationOut:
    conversation = await get_or_create_conversation(
        db, conversation_id=None, user=user, channel=payload.channel,
        language=payload.language, anonymous_key=payload.anonymous_key,
        metadata=payload.metadata,
    )
    return ConversationOut.model_validate(conversation)


@router.get("/conversations", response_model=Page[ConversationOut])
async def list_conversations(
    db: DbSession,
    user: CurrentUser,
    page: Pagination,
    status_filter: str | None = Query(None, alias="status"),
    channel: str | None = None,
    escalated_only: bool = False,
    assigned_to_me: bool = Query(False, description="Staff only: threads assigned to me"),
) -> Page[ConversationOut]:
    is_staff = user.role in (UserRole.AGENT, UserRole.SUPERVISOR, UserRole.ADMIN)

    stmt = select(Conversation).order_by(desc(Conversation.updated_at))
    count_stmt = select(func.count(Conversation.id))

    filters = []
    if not is_staff:
        # Customers only ever see their own threads.
        filters.append(Conversation.customer_id == user.id)
    elif assigned_to_me:
        filters.append(Conversation.assigned_agent_id == user.id)
    if status_filter:
        filters.append(Conversation.status == status_filter)
    if channel:
        filters.append(Conversation.channel == channel)
    if escalated_only:
        filters.append(Conversation.is_escalated.is_(True))

    for f in filters:
        stmt = stmt.where(f)
        count_stmt = count_stmt.where(f)

    rows = (
        await db.execute(stmt.limit(page.page_size).offset(page.offset))
    ).scalars().all()
    total = int((await db.execute(count_stmt)).scalar_one())

    return Page[ConversationOut](
        items=[ConversationOut.model_validate(c) for c in rows],
        total=total, page=page.page, page_size=page.page_size,
    )


@router.get("/conversations/{conversation_id}", response_model=ConversationDetail)
async def get_conversation(
    conversation_id: str, db: DbSession, user: OptionalUser
) -> ConversationDetail:
    conversation = (
        await db.execute(select(Conversation).where(Conversation.id == conversation_id))
    ).scalars().first()
    if not conversation:
        raise NotFoundError("Conversation not found.")
    _assert_can_view(user, conversation)

    messages = (
        await db.execute(
            select(Message)
            .where(Message.conversation_id == conversation_id,
                   Message.role != MessageRole.SYSTEM)
            .order_by(Message.created_at)
        )
    ).scalars().all()

    detail = ConversationDetail.model_validate(conversation)
    detail.messages = [MessageOut.model_validate(m) for m in messages]
    return detail


@router.post("/conversations/{conversation_id}/close", response_model=Msg)
async def close(conversation_id: str, db: DbSession, user: OptionalUser) -> Msg:
    conversation = (
        await db.execute(select(Conversation).where(Conversation.id == conversation_id))
    ).scalars().first()
    if not conversation:
        raise NotFoundError("Conversation not found.")
    _assert_can_view(user, conversation)
    await close_conversation(db, conversation)
    return Msg(message="Conversation closed.")


@router.post("/conversations/{conversation_id}/handoff", response_model=dict)
async def request_handoff(
    conversation_id: str, payload: HandoffRequest, db: DbSession, user: OptionalUser
) -> dict:
    """Explicit 'talk to a human' button in the UI."""
    conversation = (
        await db.execute(select(Conversation).where(Conversation.id == conversation_id))
    ).scalars().first()
    if not conversation:
        raise NotFoundError("Conversation not found.")
    _assert_can_view(user, conversation)

    if conversation.is_escalated:
        return {"already_escalated": True, "conversation_id": conversation.id}

    ticket = await tickets_service.escalate_conversation(
        db, conversation,
        reason=payload.reason or EscalationReason.CUSTOMER_REQUEST,
        summary=payload.note or "Customer used the 'talk to a human' control.",
    )
    depth = await tickets_service.queue_depth(db)

    db.add(
        Message(
            conversation_id=conversation.id,
            role=MessageRole.ASSISTANT,
            content=(
                "I'm connecting you with a human colleague now. Your reference is "
                f"**{ticket.ticket_number}** - they can see this whole conversation."
            ),
        )
    )
    conversation.message_count += 1
    await db.flush()

    return {
        "escalated": True,
        "ticket_number": ticket.ticket_number,
        "priority": ticket.priority,
        "queue_position": max(1, depth),
        "estimated_wait_minutes": max(2, depth * 3),
    }


@router.post("/conversations/{conversation_id}/reply", response_model=MessageOut)
async def human_agent_reply(
    conversation_id: str, payload: dict, db: DbSession, agent: StaffUser
) -> MessageOut:
    """A human agent posts into an escalated thread from the agent console."""
    conversation = (
        await db.execute(select(Conversation).where(Conversation.id == conversation_id))
    ).scalars().first()
    if not conversation:
        raise NotFoundError("Conversation not found.")

    content = (payload.get("content") or "").strip()
    if not content:
        raise NotFoundError("A reply cannot be empty.")

    message = Message(
        conversation_id=conversation.id,
        role=MessageRole.HUMAN_AGENT,
        content=content,
    )
    db.add(message)
    conversation.message_count += 1
    conversation.assigned_agent_id = agent.id
    await db.flush()
    return MessageOut.model_validate(message)


# ---------------------------------------------------------------------------
# Feedback
# ---------------------------------------------------------------------------
@router.post("/conversations/{conversation_id}/feedback", response_model=FeedbackOut,
             status_code=status.HTTP_201_CREATED)
async def submit_feedback(
    conversation_id: str, payload: FeedbackRequest, db: DbSession, user: OptionalUser
) -> FeedbackOut:
    conversation = (
        await db.execute(select(Conversation).where(Conversation.id == conversation_id))
    ).scalars().first()
    if not conversation:
        raise NotFoundError("Conversation not found.")
    _assert_can_view(user, conversation)

    existing = (
        await db.execute(select(Feedback).where(Feedback.conversation_id == conversation_id))
    ).scalars().first()

    if existing:
        existing.rating = payload.rating
        existing.resolved = payload.resolved
        existing.comment = payload.comment
        existing.nps = payload.nps
        feedback = existing
    else:
        feedback = Feedback(
            conversation_id=conversation_id,
            rating=payload.rating,
            resolved=payload.resolved,
            comment=payload.comment,
            nps=payload.nps,
        )
        db.add(feedback)

    if payload.resolved and not conversation.is_escalated:
        await tickets_service.resolve_conversation(db, conversation, by_ai=True)

    await db.flush()
    return FeedbackOut.model_validate(feedback)
