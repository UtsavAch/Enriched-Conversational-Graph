"""External document ingestion and retrieval preview.

Kept in the app so a user can drop a PDF in through the UI. Note that ingestion
is *out of band* - it does not run on the per-turn path and therefore does not
count against the bounded-per-turn-cost constraint.
"""

from __future__ import annotations

import logging
import shutil
import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from app.backend.dependencies import (
    get_document_repository,
    get_ingestor,
    get_rag_retriever,
)
from core.persistence import (
    JsonDocumentRepository,
    document_usage_map,
    find_conversations_referencing_document,
)
from core.retrieval.rag import DocumentIngestor, SimpleRagRetriever

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/documents", tags=["documents"])


@router.get("")
def list_documents(
    repo: JsonDocumentRepository = Depends(get_document_repository),
) -> list[dict]:
    """Every global document, each tagged with which conversations use it.

    ``used_by`` lets the UI grey out deletion for an in-use document instead
    of only failing after the click - the DELETE route below is the real
    guard either way, this is just the proactive hint.
    """
    usage = document_usage_map()
    out = []
    for s in repo.list_sources():
        d = s.model_dump(mode="json")
        d["used_by"] = usage.get(s.id, [])
        out.append(d)
    return out


@router.post("/upload")
async def upload_document(
    file: UploadFile = File(...),
    conversation_id: str | None = Form(None),
    ingestor: DocumentIngestor = Depends(get_ingestor),
    retriever: SimpleRagRetriever = Depends(get_rag_retriever),
) -> dict:
    """Ingest an uploaded PDF/text file.

    The upload is written to a temp file first because the loaders take a path -
    pypdf needs random access, not a stream. The temp file is removed either way.

    ``conversation_id``: when given, also copies the file into that
    conversation's ``documents/`` folder for archival purposes. The document
    still joins the global, conversation-agnostic retrieval corpus either way.
    """
    suffix = Path(file.filename or "upload").suffix
    tmp = Path(tempfile.mkstemp(suffix=suffix)[1])
    try:
        with tmp.open("wb") as fh:
            shutil.copyfileobj(file.file, fh)
        source = ingestor.ingest(
            tmp, title=Path(file.filename or tmp.name).stem, conversation_id=conversation_id
        )
    except (ValueError, RuntimeError) as exc:
        # Expected, diagnosable failures (bad file type, no extractable text).
        # Logged at WARNING with the traceback so the real cause shows up in
        # the server console, not just "400 Bad Request" in the access log.
        logger.warning(
            "document upload rejected: file=%r conversation_id=%r",
            file.filename, conversation_id, exc_info=exc,
        )
        raise HTTPException(400, str(exc)) from exc
    except Exception as exc:
        # Anything else is a bug, not a bad upload - log it loudly and still
        # tell the caller *something* rather than a bare 500 with no detail.
        logger.exception(
            "document upload crashed unexpectedly: file=%r conversation_id=%r",
            file.filename, conversation_id,
        )
        raise HTTPException(500, f"upload failed unexpectedly: {exc}") from exc
    finally:
        tmp.unlink(missing_ok=True)

    # The retriever caches all chunks in memory; new documents are invisible
    # until it is told to reload.
    retriever.refresh()
    return source.model_dump(mode="json")


@router.get("/search")
def search_documents(
    q: str,
    k: int = 5,
    retriever: SimpleRagRetriever = Depends(get_rag_retriever),
) -> list[dict]:
    """Preview what the RAG layer would retrieve for a query.

    Diagnostic endpoint, not used in the answer path. Useful when a grounded
    answer looks wrong and you need to know whether retrieval or generation was
    at fault.
    """
    return [
        {
            "chunk_id": rc.chunk.id,
            "source_id": rc.chunk.source_id,
            "source_title": rc.source_title,
            "page": rc.chunk.page,
            "score": round(rc.score, 4),
            "text": rc.chunk.text,
        }
        for rc in retriever.retrieve(q, k=k)
    ]


@router.delete("/{source_id}")
def delete_document(
    source_id: str,
    repo: JsonDocumentRepository = Depends(get_document_repository),
    retriever: SimpleRagRetriever = Depends(get_rag_retriever),
) -> dict:
    """Delete a global document - refused while any conversation has a claim on it.

    Deleting it out from under a conversation that depends on it would
    silently break that conversation's retrieval, and worse, invalidate the
    provenance of any past answer that already cited it. Deselecting is
    deliberately *not* enough to clear this - a deselected document's archive
    stays in the conversation's folder precisely so its evaluation record
    survives (see ``find_conversations_referencing_document``). The only fix
    is deleting the conversations that still hold it.
    """
    referencing = find_conversations_referencing_document(source_id)
    if referencing:
        raise HTTPException(
            409,
            f"'{source_id}' is still held by: {', '.join(referencing)}. "
            "Deselecting won't release it - delete those conversations first.",
        )
    repo.delete_source(source_id)
    retriever.refresh()
    return {"deleted": source_id}
