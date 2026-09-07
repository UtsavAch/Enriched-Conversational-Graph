"""External document ingestion and retrieval preview.

Kept in the app so a user can drop a PDF in through the UI. Note that ingestion
is *out of band* - it does not run on the per-turn path and therefore does not
count against the bounded-per-turn-cost constraint.
"""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from app.backend.dependencies import (
    get_document_repository,
    get_ingestor,
    get_rag_retriever,
)
from core.persistence import JsonDocumentRepository
from core.retrieval.rag import DocumentIngestor, SimpleRagRetriever

router = APIRouter(prefix="/api/documents", tags=["documents"])


@router.get("")
def list_documents(
    repo: JsonDocumentRepository = Depends(get_document_repository),
) -> list[dict]:
    return [s.model_dump(mode="json") for s in repo.list_sources()]


@router.post("/upload")
async def upload_document(
    file: UploadFile = File(...),
    ingestor: DocumentIngestor = Depends(get_ingestor),
    retriever: SimpleRagRetriever = Depends(get_rag_retriever),
) -> dict:
    """Ingest an uploaded PDF/text file.

    The upload is written to a temp file first because the loaders take a path -
    pypdf needs random access, not a stream. The temp file is removed either way.
    """
    suffix = Path(file.filename or "upload").suffix
    tmp = Path(tempfile.mkstemp(suffix=suffix)[1])
    try:
        with tmp.open("wb") as fh:
            shutil.copyfileobj(file.file, fh)
        source = ingestor.ingest(tmp, title=Path(file.filename or tmp.name).stem)
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(400, str(exc)) from exc
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
    repo.delete_source(source_id)
    retriever.refresh()
    return {"deleted": source_id}
