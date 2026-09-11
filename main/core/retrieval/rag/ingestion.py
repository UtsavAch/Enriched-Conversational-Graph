"""Document ingestion: file in, embedded chunks out.

Deliberately narrow scope. One loader (PDF) plus a plain-text fallback, fixed
chunking, one embedding pass, one write. No OCR, no table extraction, no layout
analysis, no incremental re-indexing.

EXTENDING THIS LATER (the expected path):

* more file types  -> add a function to ``LOADERS``. Nothing else changes.
* a database source -> write a loader that yields ``(page, text)`` from rows.
  ``DocumentSource.source_type`` already exists to distinguish them.
* better chunking  -> swap the call to ``chunk_text``; the storage schema is
  unaffected because a chunk is just text + provenance.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Callable, Iterable

from core.config import RagConfig
from core.llm.embeddings import Embedder
from core.persistence.json_repository import JsonDocumentRepository
from core.retrieval.rag.chunking import TextSpan, chunk_text
from core.schema.document import DocumentChunk, DocumentSource

logger = logging.getLogger(__name__)

#: A loader yields ``(page_number_or_None, page_text)`` pairs.
PageIterator = Iterable[tuple[int | None, str]]


def load_pdf(path: Path) -> PageIterator:
    """Extract text per page using pypdf.

    Page numbers are kept because "which page did this come from" is the first
    thing anyone asks of a document citation, and reconstructing it later from
    character offsets is miserable.

    A PDF with no text layer (a scan) yields empty strings. That is reported by
    the caller rather than silently producing zero chunks, because "I ingested
    it and got nothing" is a confusing failure to debug. Text-only, on purpose:
    no OCR, no image extraction - a scanned PDF needs to be OCR'd elsewhere
    before ingestion.
    """
    try:
        from pypdf import PdfReader  # noqa: PLC0415
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError(
            "pypdf is required to ingest PDFs: pip install pypdf"
        ) from exc

    reader = PdfReader(str(path))
    for i, page in enumerate(reader.pages, start=1):
        yield i, page.extract_text() or ""


def load_text(path: Path) -> PageIterator:
    """Plain text / markdown. One 'page'."""
    yield None, path.read_text(encoding="utf-8", errors="replace")


LOADERS: dict[str, Callable[[Path], PageIterator]] = {
    ".pdf": load_pdf,
    ".txt": load_text,
    ".md": load_text,
}


class DocumentIngestor:
    """Turns a file into stored, embedded chunks.

    Not a pipeline step: ingestion happens out of band, once per document, not
    per conversation turn. Keeping it off the per-turn path is what stops it
    from touching the bounded-per-turn-cost constraint.
    """

    def __init__(
        self,
        repository: JsonDocumentRepository,
        embedder: Embedder,
        config: RagConfig | None = None,
    ) -> None:
        self.repository = repository
        self.embedder = embedder
        self.config = config or RagConfig()

    def ingest(
        self,
        path: Path | str,
        *,
        title: str | None = None,
        metadata: dict | None = None,
        conversation_id: str | None = None,
    ) -> DocumentSource:
        """Ingest one file. Returns the stored ``DocumentSource``.

        Raises ``ValueError`` for an unsupported extension or a file that
        produced no usable text, rather than storing an empty source that would
        silently never match anything.

        ``conversation_id``: when given, also copies ``path`` into that
        conversation's ``documents/`` folder (see
        ``attach_document_to_conversation``). Purely archival - retrieval keeps
        reading from the global ``data/documents/`` store regardless.
        """
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(path)

        loader = LOADERS.get(path.suffix.lower())
        if loader is None:
            raise ValueError(
                f"unsupported file type '{path.suffix}'. "
                f"Supported: {sorted(LOADERS)}. Add a loader to LOADERS to extend."
            )

        spans: list[TextSpan] = []
        for page_no, page_text in loader(path):
            spans.extend(
                chunk_text(
                    page_text,
                    chunk_size=self.config.chunk_size_chars,
                    overlap=self.config.chunk_overlap_chars,
                    min_chunk=self.config.min_chunk_chars,
                    page=page_no,
                )
            )

        if not spans:
            raise ValueError(
                f"'{path.name}' produced no text chunks. If it is a scanned PDF "
                "it has no text layer - OCR it elsewhere first, then ingest the result."
            )

        source_id = self.repository.next_source_id()
        vectors = self.embedder.embed([s.text for s in spans])

        chunks = [
            DocumentChunk(
                id=f"{source_id}:{i}",
                source_id=source_id,
                chunk_index=i,
                text=span.text,
                embedding=vector,
                page=span.page,
            )
            for i, (span, vector) in enumerate(zip(spans, vectors))
        ]

        source = DocumentSource(
            id=source_id,
            title=title or path.stem,
            source_type="pdf" if path.suffix.lower() == ".pdf" else "text",
            uri=str(path.resolve()),
            metadata=metadata or {},
        )
        self.repository.add_source(source, chunks)
        logger.info("ingested %s as %s (%d chunks)", path.name, source_id, len(chunks))

        # Archive the original bytes globally - add_source only persisted the
        # chunked/embedded text. Without this, an API upload's raw file is
        # gone for good the moment the request's temp file is cleaned up.
        from core.persistence.json_repository import save_source_file  # noqa: PLC0415

        save_source_file(source, path)

        if conversation_id:
            from core.persistence.json_repository import (  # noqa: PLC0415
                attach_document_to_conversation,
            )

            attach_document_to_conversation(conversation_id, path, source)
            logger.info("attached %s to conversation '%s'", source_id, conversation_id)

        return source
