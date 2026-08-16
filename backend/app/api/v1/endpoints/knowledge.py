"""Knowledge-base CRUD and the RAG search / reindex endpoints."""

from __future__ import annotations

import re
import time

from fastapi import APIRouter, Query, status
from sqlalchemy import desc, func, select

from app.api.deps import DbSession, Pagination, StaffUser
from app.core.exceptions import ConflictError, NotFoundError
from app.models.knowledge import KBDocument
from app.schemas.common import Msg, Page
from app.schemas.knowledge import (
    CreateKBDocument,
    KBDocumentOut,
    KBDocumentSummary,
    KBSearchHit,
    KBSearchResponse,
    ReindexResponse,
    UpdateKBDocument,
)
from app.services import rag

router = APIRouter()


def slugify(title: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    return slug[:120] or "article"


@router.get("/search", response_model=KBSearchResponse)
async def search_kb(
    db: DbSession,
    q: str = Query(..., min_length=2, description="Natural-language question"),
    top_k: int = Query(5, ge=1, le=20),
    category: str | None = None,
) -> KBSearchResponse:
    started = time.perf_counter()
    hits = await rag.search(db, q, top_k=top_k, category=category)
    return KBSearchResponse(
        query=q,
        hits=[KBSearchHit(**h) for h in hits],
        took_ms=int((time.perf_counter() - started) * 1000),
    )


@router.get("/stats")
async def stats(db: DbSession) -> dict:
    return await rag.index_stats(db)


@router.post("/reindex", response_model=ReindexResponse)
async def reindex(db: DbSession, staff: StaffUser) -> ReindexResponse:
    """Rebuild every chunk embedding. Run after bulk edits or a model change."""
    return ReindexResponse(**await rag.reindex_all(db))


@router.get("", response_model=Page[KBDocumentSummary])
async def list_documents(
    db: DbSession,
    page: Pagination,
    category: str | None = None,
    q: str | None = None,
    published_only: bool = True,
) -> Page[KBDocumentSummary]:
    stmt = select(KBDocument)
    count_stmt = select(func.count(KBDocument.id))
    filters = []

    if published_only:
        filters.append(KBDocument.is_published.is_(True))
    if category:
        filters.append(KBDocument.category == category)
    if q:
        like = f"%{q.strip()}%"
        filters.append(KBDocument.title.ilike(like) | KBDocument.content.ilike(like))

    for f in filters:
        stmt = stmt.where(f)
        count_stmt = count_stmt.where(f)

    rows = (
        await db.execute(
            stmt.order_by(desc(KBDocument.view_count)).limit(page.page_size).offset(page.offset)
        )
    ).scalars().all()
    total = int((await db.execute(count_stmt)).scalar_one())

    return Page[KBDocumentSummary](
        items=[KBDocumentSummary.model_validate(d) for d in rows],
        total=total, page=page.page, page_size=page.page_size,
    )


@router.get("/categories")
async def categories(db: DbSession) -> list[dict]:
    rows = (
        await db.execute(
            select(KBDocument.category, func.count(KBDocument.id))
            .group_by(KBDocument.category)
            .order_by(desc(func.count(KBDocument.id)))
        )
    ).all()
    return [{"category": c, "count": int(n)} for c, n in rows]


@router.get("/{identifier}", response_model=KBDocumentOut)
async def get_document(identifier: str, db: DbSession) -> KBDocumentOut:
    doc = (
        await db.execute(
            select(KBDocument).where(
                (KBDocument.id == identifier) | (KBDocument.slug == identifier)
            )
        )
    ).scalars().first()
    if not doc:
        raise NotFoundError("Article not found.")
    doc.view_count += 1
    await db.flush()
    return KBDocumentOut.model_validate(doc)


@router.post("", response_model=KBDocumentOut, status_code=status.HTTP_201_CREATED)
async def create_document(
    payload: CreateKBDocument, db: DbSession, staff: StaffUser
) -> KBDocumentOut:
    slug = slugify(payload.title)
    existing = (
        await db.execute(select(KBDocument).where(KBDocument.slug == slug))
    ).scalars().first()
    if existing:
        raise ConflictError("An article with a very similar title already exists.")

    doc = KBDocument(
        title=payload.title,
        slug=slug,
        content=payload.content,
        category=payload.category,
        language=payload.language,
        tags=payload.tags,
        is_published=payload.is_published,
    )
    db.add(doc)
    await db.flush()
    await rag.index_document(db, doc)     # embed immediately - no stale index
    return KBDocumentOut.model_validate(doc)


@router.patch("/{document_id}", response_model=KBDocumentOut)
async def update_document(
    document_id: str, payload: UpdateKBDocument, db: DbSession, staff: StaffUser
) -> KBDocumentOut:
    doc = (
        await db.execute(select(KBDocument).where(KBDocument.id == document_id))
    ).scalars().first()
    if not doc:
        raise NotFoundError("Article not found.")

    content_changed = False
    if payload.title:
        doc.title = payload.title
        content_changed = True
    if payload.content:
        doc.content = payload.content
        content_changed = True
    if payload.category:
        doc.category = payload.category
    if payload.tags is not None:
        doc.tags = payload.tags
    if payload.is_published is not None:
        doc.is_published = payload.is_published

    if content_changed:
        doc.version += 1
        await rag.index_document(db, doc)

    await db.flush()
    return KBDocumentOut.model_validate(doc)


@router.delete("/{document_id}", response_model=Msg)
async def delete_document(document_id: str, db: DbSession, staff: StaffUser) -> Msg:
    doc = (
        await db.execute(select(KBDocument).where(KBDocument.id == document_id))
    ).scalars().first()
    if not doc:
        raise NotFoundError("Article not found.")
    await db.delete(doc)
    return Msg(message=f"Deleted '{doc.title}'.")


@router.post("/{document_id}/helpful", response_model=Msg)
async def mark_helpful(document_id: str, db: DbSession) -> Msg:
    doc = (
        await db.execute(select(KBDocument).where(KBDocument.id == document_id))
    ).scalars().first()
    if not doc:
        raise NotFoundError("Article not found.")
    doc.helpful_count += 1
    await db.flush()
    return Msg(message="Thanks for the feedback.")
