"""External-document RAG. Deliberately separate from the conversation graph.

Read ``core/schema/document.py`` for the reasoning. In one line: document chunks
are a different kind of thing from dialogue turns, discourse relations are not
defined over them, and keeping their context-budget accounting separate is what
keeps the thesis' displacement analysis interpretable.
"""

from core.retrieval.rag.chunking import TextSpan, chunk_text, normalise_whitespace
from core.retrieval.rag.ingestion import DocumentIngestor
from core.retrieval.rag.rag_retriever import RetrievedChunk, SimpleRagRetriever

__all__ = [
    "DocumentIngestor",
    "RetrievedChunk",
    "SimpleRagRetriever",
    "TextSpan",
    "chunk_text",
    "normalise_whitespace",
]
