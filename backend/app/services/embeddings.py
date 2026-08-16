"""Text embeddings for the retrieval index.

Default provider is `hashing`: a dependency-free, deterministic bag-of-features
embedder (word unigrams + bigrams + character 4-grams, hashed into a fixed
vector, sub-linear term weighting, L2-normalised). It needs no model download,
runs in microseconds and gives solid lexical recall over a support knowledge
base of a few thousand chunks.

Set `EMBEDDING_PROVIDER=sentence-transformers` for dense semantic embeddings
once `sentence-transformers` is installed.
"""

from __future__ import annotations

import abc
import hashlib
import math
import re
from functools import lru_cache

import numpy as np

from app.core.config import settings
from app.core.logging import get_logger

log = get_logger(__name__)

_TOKEN_RE = re.compile(r"[a-z0-9]+")

STOPWORDS = {
    "a", "about", "after", "all", "an", "and", "any", "are", "as", "at", "be",
    "been", "before", "but", "by", "can", "could", "did", "do", "does", "for",
    "from", "get", "got", "had", "has", "have", "here", "how", "i", "if", "in",
    "into", "is", "it", "its", "many", "me", "much", "my", "no", "not", "of",
    "on", "or", "our", "please", "should", "so", "some", "than", "that", "the",
    "their", "them", "then", "there", "these", "they", "this", "to", "us", "was",
    "we", "were", "what", "when", "where", "which", "who", "will", "with",
    "would", "you", "your",
}

_DOUBLE_END = re.compile(r"([bdfglmnprt])\1$")


def stem(token: str) -> str:
    """A deliberately small suffix stripper.

    Support queries and help articles disagree constantly on word form -
    "cancel" vs "cancelling", "return" vs "returns", "ship" vs "shipped" - and
    without folding them together the lexical half of hybrid search misses the
    right article entirely. A full Porter stemmer would be overkill here (and
    would pull in another dependency), so these six rules cover the cases that
    actually occur in retail support text.
    """
    if len(token) <= 3 or token.isdigit():
        return token
    if token.endswith("ies") and len(token) > 4:
        return token[:-3] + "y"
    if token.endswith("ing") and len(token) > 5:
        token = token[:-3]
    elif token.endswith("ed") and len(token) > 4:
        token = token[:-2]
    elif token.endswith("es") and len(token) > 4:
        token = token[:-2]
    elif token.endswith("s") and not token.endswith("ss") and len(token) > 3:
        token = token[:-1]
    return _DOUBLE_END.sub(r"\1", token)


def tokenize(text: str) -> list[str]:
    """Lower-case, drop stopwords, stem. Shared by the embedder and the lexical
    re-ranker so both halves of hybrid search see the same vocabulary."""
    return [
        stem(t)
        for t in _TOKEN_RE.findall(text.lower())
        if t not in STOPWORDS and len(t) > 1
    ]


class BaseEmbedder(abc.ABC):
    name: str = "base"
    dim: int = 384

    @abc.abstractmethod
    def embed(self, texts: list[str]) -> np.ndarray:
        """Return an (n, dim) L2-normalised float32 matrix."""

    def embed_one(self, text: str) -> list[float]:
        return self.embed([text])[0].tolist()


class HashingEmbedder(BaseEmbedder):
    name = "hashing-v1"

    def __init__(self, dim: int | None = None) -> None:
        self.dim = dim or settings.EMBEDDING_DIM

    # ---------------------------------------------------------------- utils --
    def _bucket(self, feature: str) -> tuple[int, float]:
        digest = hashlib.blake2b(feature.encode("utf-8"), digest_size=8).digest()
        value = int.from_bytes(digest, "big")
        # Signed hashing keeps collisions from systematically inflating scores.
        return value % self.dim, 1.0 if (value >> 63) & 1 else -1.0

    def _features(self, text: str) -> dict[str, float]:
        tokens = tokenize(text)
        feats: dict[str, float] = {}

        for tok in tokens:
            feats[f"w:{tok}"] = feats.get(f"w:{tok}", 0.0) + 1.0
        for a, b in zip(tokens, tokens[1:]):
            key = f"b:{a}_{b}"
            feats[key] = feats.get(key, 0.0) + 1.2          # bigrams carry more signal
        compact = " ".join(tokens)
        for i in range(len(compact) - 3):
            key = f"c:{compact[i:i + 4]}"
            feats[key] = feats.get(key, 0.0) + 0.35          # typo / morphology robustness
        return feats

    # ---------------------------------------------------------------- public --
    def embed(self, texts: list[str]) -> np.ndarray:
        out = np.zeros((len(texts), self.dim), dtype=np.float32)
        for row, text in enumerate(texts):
            for feature, count in self._features(text).items():
                idx, sign = self._bucket(feature)
                out[row, idx] += sign * (1.0 + math.log(count))   # sub-linear TF
            norm = float(np.linalg.norm(out[row]))
            if norm > 0:
                out[row] /= norm
        return out


class SentenceTransformerEmbedder(BaseEmbedder):
    def __init__(self) -> None:
        from sentence_transformers import SentenceTransformer

        self._model = SentenceTransformer(settings.EMBEDDING_MODEL)
        self.dim = int(self._model.get_sentence_embedding_dimension())
        self.name = settings.EMBEDDING_MODEL

    def embed(self, texts: list[str]) -> np.ndarray:
        vecs = self._model.encode(
            texts, normalize_embeddings=True, convert_to_numpy=True, show_progress_bar=False
        )
        return vecs.astype(np.float32)


@lru_cache
def get_embedder() -> BaseEmbedder:
    if settings.EMBEDDING_PROVIDER == "sentence-transformers":
        try:
            embedder = SentenceTransformerEmbedder()
            log.info("Embeddings: %s (dim=%d)", embedder.name, embedder.dim)
            return embedder
        except Exception as exc:
            log.warning("sentence-transformers unavailable (%s) - using hashing embedder.", exc)
    embedder = HashingEmbedder()
    log.info("Embeddings: %s (dim=%d)", embedder.name, embedder.dim)
    return embedder


def cosine(a: list[float] | np.ndarray, b: list[float] | np.ndarray) -> float:
    va, vb = np.asarray(a, dtype=np.float32), np.asarray(b, dtype=np.float32)
    denom = float(np.linalg.norm(va) * np.linalg.norm(vb))
    return 0.0 if denom == 0 else float(np.dot(va, vb) / denom)
