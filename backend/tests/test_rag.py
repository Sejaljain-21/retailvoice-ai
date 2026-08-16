"""Retrieval tests: chunking, embedding properties and search relevance."""

from __future__ import annotations

import numpy as np
import pytest

from app.services import rag
from app.services.embeddings import HashingEmbedder, cosine, get_embedder


def test_chunking_respects_size_and_keeps_content() -> None:
    text = "\n\n".join(f"Paragraph {i}. " + "word " * 60 for i in range(8))
    chunks = rag.chunk_text(text, chunk_size=400, overlap=50)
    assert len(chunks) > 1
    assert all(len(c) <= 600 for c in chunks)
    assert "Paragraph 0" in chunks[0]


def test_chunking_splits_a_single_huge_paragraph() -> None:
    text = " ".join(f"Sentence number {i} about returns." for i in range(120))
    chunks = rag.chunk_text(text, chunk_size=300, overlap=40)
    assert len(chunks) > 3


def test_embeddings_are_normalised_and_deterministic() -> None:
    embedder = HashingEmbedder(dim=128)
    a = embedder.embed(["return policy for damaged items"])[0]
    b = embedder.embed(["return policy for damaged items"])[0]
    assert np.allclose(a, b)
    assert pytest.approx(float(np.linalg.norm(a)), abs=1e-5) == 1.0


def test_similar_texts_score_higher_than_unrelated() -> None:
    embedder = get_embedder()
    query = embedder.embed(["how do I return a damaged product"])[0]
    close = embedder.embed(["returning a damaged or defective item"])[0]
    far = embedder.embed(["mountain bike gear ratios and frame sizes"])[0]
    assert cosine(query, close) > cosine(query, far)


async def test_search_finds_the_refund_policy(db) -> None:
    hits = await rag.search(db, "how long does a refund take on UPI", top_k=3)
    assert hits, "the seeded knowledge base should answer this"
    assert any("refund" in h["title"].lower() for h in hits)
    assert hits[0]["score"] >= hits[-1]["score"]


async def test_search_finds_the_return_window(db) -> None:
    hits = await rag.search(db, "how many days do I have to return an item", top_k=3)
    assert hits
    assert any(h["category"] == "returns" for h in hits)


async def test_search_returns_nothing_for_an_empty_query(db) -> None:
    assert await rag.search(db, "   ") == []


async def test_index_stats(db) -> None:
    stats = await rag.index_stats(db)
    assert stats["documents"] >= 10
    assert stats["chunks"] >= stats["documents"]
