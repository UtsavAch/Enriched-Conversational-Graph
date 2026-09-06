"""External document sources and chunks - the simple RAG layer.

DESIGN NOTE (read this before extending):

Document chunks are a *separate node kind*. They are not interaction nodes and
they do not participate in hierarchical or pragmatic relations. The only link
between a document chunk and the conversation graph is
``InteractionNode.grounded_by``, a flat provenance list.

Why keep them apart:

1. ``subcase`` / ``contradicts`` and friends are defined as relations *between
   turns of a dialogue*. Applying them to a turn/PDF-paragraph pair silently
   changes what those labels mean, which would make Phase 3 relation-accuracy
   numbers describe two different tasks at once.
2. The thesis' displacement analysis (chapter 4) depends on knowing exactly
   which content is competing for the fixed context budget. A second content
   source sharing the same slots without separate accounting makes that
   analysis uninterpretable.

So: documents get their own store, their own retriever, and their own slice of
the context budget. If Phase 3/4 data later shows a genuine interaction between
document grounding and the discourse graph, that is a new thin edge type - not a
sixth pragmatic relation.
"""

from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel, Field


class DocumentSource(BaseModel):
    """One ingested external file (a PDF today; a DB row or URL later)."""

    id: str = Field(..., description="Stable id, convention 'DOC_<n>'.")
    title: str
    source_type: str = Field(
        "pdf",
        description="'pdf' today. The field exists so adding 'database' or "
        "'web' later is not a schema migration.",
    )
    uri: str = Field(..., description="Path or URL the content came from.")
    n_chunks: int = 0
    ingested_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    metadata: dict[str, str] = Field(
        default_factory=dict, description="Free-form: author, year, section, ..."
    )


class DocumentChunk(BaseModel):
    """A retrievable span of an external document.

    Kept deliberately flat. There is no chunk graph, no parent/child hierarchy,
    no chunk-to-chunk edges. If chunk structure turns out to matter, that is a
    separate piece of work with its own justification.
    """

    id: str = Field(..., description="Stable id, convention 'DOC_<n>:<chunk_index>'.")
    source_id: str
    chunk_index: int = Field(..., ge=0)
    text: str
    embedding: list[float] | None = None
    page: int | None = Field(None, description="1-based page number, if known.")

    def citation_label(self, source_title: str | None = None) -> str:
        """Short human-readable provenance string for prompt injection."""
        title = source_title or self.source_id
        page = f", p.{self.page}" if self.page is not None else ""
        return f"{title}{page}"

    def render(self) -> str:
        """How this chunk appears when injected into an answer-generation prompt."""
        return f"[{self.id}] {self.text}"
