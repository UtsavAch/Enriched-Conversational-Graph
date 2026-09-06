"""Repository interfaces.

Everything above this layer - pipeline, evaluation harness, app backend - talks
to these Protocols and never to a file path or a database cursor. That is what
makes "JSON now, Postgres or a vector DB later" a matter of writing one new
class rather than editing the pipeline.

Protocols (structural typing) rather than ABCs, so an implementation does not
have to inherit anything. A test double just has to have the right methods.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from core.schema.conversation import ConversationGraph
from core.schema.document import DocumentChunk, DocumentSource


@runtime_checkable
class ConversationRepository(Protocol):
    """Load and store whole conversation graphs.

    Deliberately coarse-grained. There is no ``add_edge`` or ``update_node``:
    the pipeline produces everything for a turn and then commits it in one go
    (``append_turn``). Fine-grained mutation methods would invite partial writes
    that leave the graph referentially inconsistent.
    """

    def list_conversations(self) -> list[str]:
        """Every conversation id currently stored."""
        ...

    def exists(self, conversation_id: str) -> bool: ...

    def load(self, conversation_id: str) -> ConversationGraph:
        """Raise ``KeyError`` if it does not exist."""
        ...

    def save(self, graph: ConversationGraph) -> None:
        """Persist the whole graph, overwriting what is there."""
        ...

    def delete(self, conversation_id: str) -> None: ...


@runtime_checkable
class DocumentRepository(Protocol):
    """Store ingested external documents and their chunks.

    Separate from ``ConversationRepository`` on purpose: documents are not
    conversation-scoped. One PDF can ground answers in many conversations, and
    tying it to one would force re-ingestion.
    """

    def list_sources(self) -> list[DocumentSource]: ...

    def get_source(self, source_id: str) -> DocumentSource: ...

    def add_source(self, source: DocumentSource, chunks: list[DocumentChunk]) -> None:
        """Store a source together with all its chunks, atomically."""
        ...

    def get_chunks(self, source_id: str) -> list[DocumentChunk]: ...

    def all_chunks(self) -> list[DocumentChunk]:
        """Every chunk across every source.

        Fine for the current scale (tens of PDFs, thousands of chunks): a linear
        cosine scan over this is milliseconds. This method is exactly where the
        cost will show up first if the corpus grows, and is the natural place to
        swap in a vector index. See ``core/retrieval/rag/rag_retriever.py``.
        """
        ...

    def delete_source(self, source_id: str) -> None: ...
