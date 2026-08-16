"""Knowledge base documents and their embedded chunks (the RAG index)."""

from __future__ import annotations

from typing import Any

from sqlalchemy import JSON, Boolean, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDMixin


class KBDocument(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "kb_documents"

    title: Mapped[str] = mapped_column(String(240), index=True)
    slug: Mapped[str] = mapped_column(String(240), unique=True, index=True)
    category: Mapped[str] = mapped_column(String(80), default="general", index=True)
    content: Mapped[str] = mapped_column(Text, default="")
    source_url: Mapped[str | None] = mapped_column(String(512))
    language: Mapped[str] = mapped_column(String(12), default="en")
    is_published: Mapped[bool] = mapped_column(Boolean, default=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    tags: Mapped[list[str]] = mapped_column(JSON, default=list)
    view_count: Mapped[int] = mapped_column(Integer, default=0)
    helpful_count: Mapped[int] = mapped_column(Integer, default=0)

    chunks: Mapped[list["KBChunk"]] = relationship(
        back_populates="document", cascade="all, delete-orphan"
    )


class KBChunk(UUIDMixin, TimestampMixin, Base):
    """A retrievable passage. `embedding` is a JSON float array (portable across
    SQLite and Postgres); swap to pgvector for production scale."""

    __tablename__ = "kb_chunks"

    document_id: Mapped[str] = mapped_column(
        ForeignKey("kb_documents.id", ondelete="CASCADE"), index=True
    )
    chunk_index: Mapped[int] = mapped_column(Integer, default=0)
    content: Mapped[str] = mapped_column(Text)
    token_estimate: Mapped[int] = mapped_column(Integer, default=0)
    embedding: Mapped[list[float]] = mapped_column(JSON, default=list)
    embedding_model: Mapped[str] = mapped_column(String(80), default="hashing-v1")
    norm: Mapped[float] = mapped_column(Float, default=0.0)
    extra: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)

    document: Mapped["KBDocument"] = relationship(back_populates="chunks")
