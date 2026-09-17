"""Embedding providers.

The thesis fixes a 768-dimensional retrieval-trained embedder compared by dot
product, after finding that a general-purpose vision-language model produced
near-zero recall on multi-hop questions. That finding is a real constraint: do
not casually swap in whatever embedder is convenient, because retrieval quality
is the thing the whole architecture rests on.

Four providers here:

* ``SentenceTransformerEmbedder`` - real, local, free. Optional dependency.
* ``GeminiEmbedder``              - real, cloud, free tier (Google AI Studio).
  The recommended pairing when the extraction/answer LLM is Groq: Groq has no
  embeddings endpoint of its own, and this is a genuinely free cloud option
  rather than a paid one (OpenAI/Voyage embeddings are not free).
* ``HashingEmbedder``            - deterministic, dependency-free, offline. Its
  vectors are meaningless for semantic similarity; it exists so the pipeline,
  the storage layer and the app can be exercised end to end without a model
  download. Never use it to produce a number you intend to report.
* ``CachingEmbedder``            - wraps any provider with an in-memory cache.
"""

from __future__ import annotations

import hashlib
import math
from typing import Protocol, runtime_checkable


@runtime_checkable
class Embedder(Protocol):
    dim: int

    def embed(self, texts: list[str]) -> list[list[float]]: ...


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Cosine similarity, guarding against zero vectors.

    Used rather than raw dot product because not every provider returns
    L2-normalised vectors. For normalised vectors the two are identical, so this
    is a safe default that stays comparable with the thesis' dot-product setup.
    """
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return dot / (na * nb)


def top_k_by_similarity(
    query: list[float],
    candidates: list[tuple[str, list[float] | None]],
    k: int,
    min_similarity: float = 0.0,
) -> list[tuple[str, float]]:
    """Rank ``(id, embedding)`` pairs against a query vector.

    Candidates with no embedding are skipped rather than scored as 0, so a node
    whose EMBED call failed simply does not compete, instead of being ranked
    last and occasionally sneaking into a small top-k.
    """
    scored = [
        (cid, cosine_similarity(query, emb))
        for cid, emb in candidates
        if emb is not None
    ]
    scored = [(cid, s) for cid, s in scored if s >= min_similarity]
    scored.sort(key=lambda t: t[1], reverse=True)
    return scored[:k]


class HashingEmbedder:
    """Deterministic pseudo-embeddings from token hashes.

    A bag-of-words hashing trick: each whitespace token is hashed into one of
    ``dim`` buckets. Two texts sharing words get similar vectors; two texts that
    mean the same thing in different words do not. That is a real limitation and
    the whole reason it is a development stand-in only.
    """

    def __init__(self, dim: int = 768) -> None:
        self.dim = dim

    def embed(self, texts: list[str]) -> list[list[float]]:
        out = []
        for text in texts:
            vec = [0.0] * self.dim
            for token in text.lower().split():
                h = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
                idx = int.from_bytes(h[:4], "big") % self.dim
                sign = 1.0 if h[4] % 2 == 0 else -1.0
                vec[idx] += sign
            norm = math.sqrt(sum(v * v for v in vec)) or 1.0
            out.append([v / norm for v in vec])
        return out


class SentenceTransformerEmbedder:
    """Real embeddings via sentence-transformers. Optional dependency."""

    def __init__(self, model_name: str, dim: int | None = None) -> None:
        try:
            from sentence_transformers import SentenceTransformer  # noqa: PLC0415
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError(
                "sentence-transformers is required for SentenceTransformerEmbedder; "
                "install it or use HashingEmbedder for offline development"
            ) from exc
        self._model = SentenceTransformer(model_name)
        self.dim = dim or self._model.get_embedding_dimension()

    def embed(self, texts: list[str]) -> list[list[float]]:
        vecs = self._model.encode(texts, normalize_embeddings=True)
        return [list(map(float, v)) for v in vecs]


class GeminiEmbedder:
    """Google Gemini embeddings, free tier, via its OpenAI-compatible endpoint.

    Reuses the ``openai`` package (already a dependency for OpenAICompatClient)
    pointed at Google's OpenAI-compatible base URL, rather than adding a
    separate Google SDK dependency for one call shape. Same account and API
    key as any Gemini chat model, but independent of which provider is used
    for extraction/answers - see core/config.py's ``gemini_api_key``.
    """

    #: Google's OpenAI-compatible endpoint (chat + embeddings).
    BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"

    def __init__(
        self, model: str = "gemini-embedding-001", api_key: str | None = None, dim: int = 768
    ) -> None:
        try:
            from openai import OpenAI  # noqa: PLC0415
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError(
                "the 'openai' package is required for GeminiEmbedder; "
                "install it with: pip install openai"
            ) from exc
        if not api_key:
            raise RuntimeError(
                "GeminiEmbedder requires an API key (GEMINI_API_KEY) - "
                "get a free one at aistudio.google.com"
            )
        self.model = model
        self.dim = dim
        self._client = OpenAI(base_url=self.BASE_URL, api_key=api_key)

    def embed(self, texts: list[str]) -> list[list[float]]:
        # dimensions= requests Matryoshka-truncated output at this project's
        # standard 768-d, so GeminiEmbedder is drop-in compatible with every
        # other Embedder here without a config.py change to embedding_dim.
        resp = self._client.embeddings.create(
            model=self.model, input=texts, dimensions=self.dim
        )
        return [item.embedding for item in resp.data]


class CachingEmbedder:
    """Memoise embeddings by exact text.

    Worth having because the same text gets embedded more than once across a
    run: a state node's label is embedded on creation and again if W4 re-emits
    it, and the evaluation harness replays conversations repeatedly.
    """

    def __init__(self, inner: Embedder) -> None:
        self._inner = inner
        self.dim = inner.dim
        self._cache: dict[str, list[float]] = {}

    def embed(self, texts: list[str]) -> list[list[float]]:
        missing = [t for t in texts if t not in self._cache]
        if missing:
            for text, vec in zip(missing, self._inner.embed(missing)):
                self._cache[text] = vec
        return [self._cache[t] for t in texts]


def build_embedder(model_name: str, dim: int = 768, api_key: str | None = None) -> Embedder:
    """Factory driven by ``ModelConfig.embedding_model``.

    ``"hashing"`` selects the offline stand-in; ``"gemini"`` selects the free
    cloud provider (``api_key`` then required - pass ``settings.models.
    gemini_api_key``); anything else is treated as a sentence-transformers
    model id.
    """
    if model_name == "hashing":
        return CachingEmbedder(HashingEmbedder(dim=dim))
    if model_name == "gemini":
        return CachingEmbedder(GeminiEmbedder(api_key=api_key, dim=dim))
    return CachingEmbedder(SentenceTransformerEmbedder(model_name, dim=dim))
