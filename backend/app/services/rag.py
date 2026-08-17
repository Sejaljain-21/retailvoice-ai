"""Retrieval-augmented generation over the support knowledge base.

Pipeline: document -> paragraph-aware chunking -> embedding -> DB.
Query time: embed query -> cosine over chunk vectors -> lexical re-rank ->
top-k passages returned as grounded citations for the agent.
"""

from __future__ import annotations

import math
import re
import time

import numpy as np
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import get_logger
from app.models.knowledge import KBChunk, KBDocument
from app.services.embeddings import get_embedder, tokenize

log = get_logger(__name__)


# ---------------------------------------------------------------------------
# Chunking
# ---------------------------------------------------------------------------
def chunk_text(
    text: str,
    chunk_size: int | None = None,
    overlap: int | None = None,
) -> list[str]:
    """Split on paragraph boundaries, packing up to `chunk_size` characters and
    carrying `overlap` characters of context into the next chunk."""
    size = chunk_size or settings.RAG_CHUNK_SIZE
    lap = overlap or settings.RAG_CHUNK_OVERLAP

    def tail(s: str, n: int) -> str:
        """Overlap carried into the next chunk.

        Snapped forward to a sentence boundary where one exists, otherwise to a
        word boundary. Without this a chunk can begin mid-sentence, and since
        chunks are shown to the customer as cited evidence, that reads as a
        broken answer even when the retrieval was correct.
        """
        if n <= 0 or len(s) <= n:
            return s
        cut = s[-n:]
        sentence = re.search(r"[.!?]\s+", cut)
        if sentence:
            return cut[sentence.end():]
        space = cut.find(" ")
        return cut[space + 1:] if space != -1 else ""

    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    chunks: list[str] = []
    buffer = ""

    for para in paragraphs:
        # A single oversized paragraph is split on sentence boundaries.
        if len(para) > size:
            if buffer:
                chunks.append(buffer.strip())
                buffer = ""
            sentences = re.split(r"(?<=[.!?])\s+", para)
            current = ""
            for sentence in sentences:
                if len(current) + len(sentence) + 1 > size and current:
                    chunks.append(current.strip())
                    current = tail(current, lap)
                current += (" " if current else "") + sentence
            if current.strip():
                buffer = current.strip()
            continue

        if len(buffer) + len(para) + 2 > size and buffer:
            chunks.append(buffer.strip())
            buffer = tail(buffer, lap)
        buffer += ("\n\n" if buffer else "") + para

    if buffer.strip():
        chunks.append(buffer.strip())
    return [c for c in chunks if len(c) > 20] or ([text.strip()] if text.strip() else [])


# ---------------------------------------------------------------------------
# Indexing
# ---------------------------------------------------------------------------
async def index_document(db: AsyncSession, document: KBDocument) -> int:
    """(Re)build the chunk index for one document. Returns the chunk count."""
    embedder = get_embedder()

    await db.execute(delete(KBChunk).where(KBChunk.document_id == document.id))

    pieces = chunk_text(document.content)
    if not pieces:
        return 0

    # Prefixing the title gives every chunk topical context.
    vectors = embedder.embed([f"{document.title}\n{p}" for p in pieces])

    for i, (piece, vector) in enumerate(zip(pieces, vectors)):
        db.add(
            KBChunk(
                document_id=document.id,
                chunk_index=i,
                content=piece,
                token_estimate=max(1, len(piece) // 4),
                embedding=[round(float(x), 6) for x in vector],
                embedding_model=embedder.name,
                norm=float(np.linalg.norm(vector)),
                extra={"title": document.title, "category": document.category},
            )
        )
    await db.flush()
    return len(pieces)


async def reindex_all(db: AsyncSession) -> dict[str, object]:
    started = time.perf_counter()
    docs = (await db.execute(select(KBDocument))).scalars().all()
    total_chunks = 0
    for doc in docs:
        total_chunks += await index_document(db, doc)
    await db.commit()
    took = int((time.perf_counter() - started) * 1000)
    log.info("Reindexed %d documents into %d chunks in %dms", len(docs), total_chunks, took)
    return {
        "documents": len(docs),
        "chunks": total_chunks,
        "embedding_model": get_embedder().name,
        "took_ms": took,
    }


# ---------------------------------------------------------------------------
# Retrieval
# ---------------------------------------------------------------------------
# Whether to weight lexical matches by inverse document frequency.
#
# MEASURED, not assumed. On the 30-question labelled set in `evaluate.py`,
# against this 14-article knowledge base:
#
#     uniform coverage   P@1 80.0 %   R@3 100 %   MRR 0.900   <- shipped
#     chunk-level IDF    P@1 76.7 %   R@3 100 %   MRR 0.878
#     document-level IDF P@1 76.7 %   R@3 100 %   MRR 0.883
#
# IDF is the textbook choice and it is genuinely needed at scale, but with 14
# documents there is nothing for it to estimate - almost every content term is
# "rare", so the weights amplify chunking accidents rather than real term
# rarity. Turn this on when the corpus reaches a few hundred articles and
# re-run `python evaluate.py` to confirm it has started paying for itself.
USE_IDF_WEIGHTING = False


def _idf_weights(query_tokens: set[str], corpus: list[set[str]]) -> dict[str, float]:
    """Inverse document frequency over the candidate set.

    Rare query terms should dominate: in "refund policy for UPI", `upi` appears
    in one article and `policy` in half of them. See `USE_IDF_WEIGHTING` for why
    this is currently disabled.
    """
    if not USE_IDF_WEIGHTING:
        return {token: 1.0 for token in query_tokens}

    n = len(corpus) or 1
    weights: dict[str, float] = {}
    for token in query_tokens:
        df = sum(1 for doc in corpus if token in doc)
        weights[token] = math.log(1 + n / (1 + df))
    return weights


def _lexical_score(
    query_tokens: set[str], doc_tokens: set[str], idf: dict[str, float]
) -> float:
    """IDF-weighted share of the query that this passage actually covers."""
    if not query_tokens or not doc_tokens:
        return 0.0
    total = sum(idf.get(t, 0.0) for t in query_tokens)
    if total <= 0:
        return 0.0
    matched = sum(idf.get(t, 0.0) for t in query_tokens & doc_tokens)
    return matched / total


async def search(
    db: AsyncSession,
    query: str,
    *,
    top_k: int | None = None,
    min_score: float | None = None,
    category: str | None = None,
) -> list[dict]:
    """Return ranked passages: chunk_id, document_id, title, slug, snippet, score."""
    k = top_k or settings.RAG_TOP_K
    floor = settings.RAG_MIN_SCORE if min_score is None else min_score
    if not query.strip():
        return []

    stmt = (
        select(KBChunk, KBDocument)
        .join(KBDocument, KBChunk.document_id == KBDocument.id)
        .where(KBDocument.is_published.is_(True))
    )
    if category:
        stmt = stmt.where(KBDocument.category == category)

    rows = (await db.execute(stmt)).all()
    if not rows:
        return []

    embedder = get_embedder()
    q_vec = np.asarray(embedder.embed([query])[0], dtype=np.float32)
    q_tokens = set(tokenize(query))

    matrix, meta = [], []
    for chunk, doc in rows:
        vec = chunk.embedding or []
        if len(vec) != q_vec.shape[0]:
            continue  # stale index from a different embedding model
        matrix.append(vec)
        meta.append((chunk, doc))
    if not matrix:
        log.warning("KB index is empty or was built with a different model - run /knowledge/reindex")
        return []

    sims = np.asarray(matrix, dtype=np.float32) @ q_vec  # both sides are L2-normalised

    body_tokens = [set(tokenize(f"{doc.title} {chunk.content}")) for chunk, doc in meta]
    title_tokens = [set(tokenize(doc.title)) for _, doc in meta]
    idf = _idf_weights(q_tokens, body_tokens)

    scored = []
    for i, (sim, (chunk, doc)) in enumerate(zip(sims, meta)):
        lexical = _lexical_score(q_tokens, body_tokens[i], idf)
        title_hit = _lexical_score(q_tokens, title_tokens[i], idf)
        # Hybrid score: dense similarity for paraphrases, IDF-weighted lexical
        # coverage for rare terms, and a title match to break topical ties.
        score = float(0.45 * float(sim) + 0.40 * lexical + 0.15 * title_hit)
        if score < floor:
            continue
        scored.append((score, chunk, doc))

    scored.sort(key=lambda t: t[0], reverse=True)

    hits: list[dict] = []
    per_doc: dict[str, int] = {}
    for score, chunk, doc in scored:
        # At most two passages from the same article keeps the context diverse.
        if per_doc.get(doc.id, 0) >= 2:
            continue
        per_doc[doc.id] = per_doc.get(doc.id, 0) + 1
        hits.append(
            {
                "chunk_id": chunk.id,
                "document_id": doc.id,
                "title": doc.title,
                "slug": doc.slug,
                "category": doc.category,
                "snippet": chunk.content[:900],
                "score": round(score, 4),
            }
        )
        if len(hits) >= k:
            break
    return hits


async def index_stats(db: AsyncSession) -> dict[str, object]:
    docs = (await db.execute(select(func.count(KBDocument.id)))).scalar_one()
    chunks = (await db.execute(select(func.count(KBChunk.id)))).scalar_one()
    return {
        "documents": int(docs),
        "chunks": int(chunks),
        "embedding_model": get_embedder().name,
        "dim": get_embedder().dim,
    }
