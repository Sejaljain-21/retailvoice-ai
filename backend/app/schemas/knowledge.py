"""Knowledge-base schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel


class KBDocumentOut(ORMModel):
    id: str
    title: str
    slug: str
    category: str
    content: str
    language: str
    is_published: bool
    version: int
    tags: list[str] = Field(default_factory=list)
    view_count: int
    helpful_count: int
    created_at: datetime
    updated_at: datetime


class KBDocumentSummary(ORMModel):
    id: str
    title: str
    slug: str
    category: str
    tags: list[str] = Field(default_factory=list)
    view_count: int
    updated_at: datetime


class CreateKBDocument(BaseModel):
    title: str = Field(min_length=3, max_length=240)
    content: str = Field(min_length=10)
    category: str = "general"
    language: str = "en"
    tags: list[str] = Field(default_factory=list)
    is_published: bool = True


class UpdateKBDocument(BaseModel):
    title: str | None = None
    content: str | None = None
    category: str | None = None
    tags: list[str] | None = None
    is_published: bool | None = None


class KBSearchHit(BaseModel):
    chunk_id: str
    document_id: str
    title: str
    slug: str
    category: str
    snippet: str
    score: float


class KBSearchResponse(BaseModel):
    query: str
    hits: list[KBSearchHit]
    took_ms: int


class ReindexResponse(BaseModel):
    documents: int
    chunks: int
    embedding_model: str
    took_ms: int
