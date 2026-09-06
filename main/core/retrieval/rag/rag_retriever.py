"""Simple document retrieval: embed the query, cosine top-k, return chunks.

That is the whole algorithm. No reranking, no query expansion, no hybrid
sparse/dense scoring, no HyDE.

WHY: this component is *support infrastructure* for the thesis, not a subject of
it. Making it sophisticated would add confounds (was the improvement from the
enriched graph, or from the reranker?) without answering the research question.
Keeping it simple and stated makes it a clean, controllable variable.

WHERE THE SCALING WALL IS: ``all_chunks()`` loads every chunk into memory and
scores it linearly. At a few thousand chunks that is single-digit milliseconds.
At a few hundred thousand it is not. The fix at that point is a vector index
behind the same ``retrieve()`` signature - which is why the linear scan is
isolated in one method here rather than inlined into the caller.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from core.config import RagConfig
from core.llm.embeddings import Embedder, cosine_similarity
from core.persistence.json_repository import JsonDocumentRepository
from core.schema.document import DocumentChunk

logger = logging.getLogger(__name__)


@dataclass
class RetrievedChunk:
    """A chunk plus its score and human-readable provenance."""

    chunk: DocumentChunk
    score: float
    source_title: str = ""

    def render(self) -> str:
        """Formatted for injection into an answer-generation prompt."""
        loc = f", p.{self.chunk.page}" if self.chunk.page is not None else ""
        return f"[{self.chunk.id}] ({self.source_title}{loc}) {self.chunk.text}"


class SimpleRagRetriever:
    """Cosine top-k over all stored document chunks."""

    def __init__(
        self,
        repository: JsonDocumentRepository,
        embedder: Embedder,
        config: RagConfig | None = None,
    ) -> None:
        self.repository = repository
        self.embedder = embedder
        self.config = config or RagConfig()
        self._cache: list[DocumentChunk] | None = None
        self._titles: dict[str, str] = {}

    def refresh(self) -> None:
        """Drop the in-memory chunk cache. Call after ingesting new documents."""
        self._cache = None
        self._titles = {}

    def _chunks(self) -> list[DocumentChunk]:
        if self._cache is None:
            self._cache = self.repository.all_chunks()
            self._titles = {s.id: s.title for s in self.repository.list_sources()}
            logger.debug("loaded %d document chunks", len(self._cache))
        return self._cache

    def retrieve(
        self,
        query: str,
        *,
        k: int | None = None,
        source_ids: list[str] | None = None,
    ) -> list[RetrievedChunk]:
        """Return the ``k`` chunks most similar to ``query``.

        Parameters
        ----------
        source_ids:
            Restrict retrieval to specific documents. Useful when a conversation
            is explicitly about one paper - it stops an unrelated PDF from
            winning a slot on a coincidental phrase match.

        Returns an empty list when no documents are ingested, rather than
        raising: a conversation with no attached documents is normal, and the
        answer-generation prompt handles an empty document section fine.
        """
        k = k if k is not None else self.config.top_k
        chunks = self._chunks()
        if source_ids is not None:
            allowed = set(source_ids)
            chunks = [c for c in chunks if c.source_id in allowed]
        if not chunks or k <= 0:
            return []

        query_vec = self.embedder.embed([query])[0]
        scored = [
            (c, cosine_similarity(query_vec, c.embedding))
            for c in chunks
            if c.embedding is not None
        ]
        scored = [(c, s) for c, s in scored if s >= self.config.min_similarity]
        scored.sort(key=lambda t: t[1], reverse=True)

        return [
            RetrievedChunk(chunk=c, score=s, source_title=self._titles.get(c.source_id, c.source_id))
            for c, s in scored[:k]
        ]
