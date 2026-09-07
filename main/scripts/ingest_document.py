"""Ingest a PDF or text file into the external-document store.

    python -m scripts.ingest_document papers/graphrag.pdf --title "GraphRAG"

Runs out of band - not on the per-turn path - so it has no bearing on the
bounded-per-turn-cost constraint.
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

from core.config import Settings
from core.llm.embeddings import build_embedder
from core.persistence import JsonDocumentRepository
from core.retrieval.rag import DocumentIngestor, SimpleRagRetriever


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="+", type=Path)
    parser.add_argument("--title", default=None, help="Only valid with a single file.")
    parser.add_argument("--preview", default=None, help="Run a test query after ingest.")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    settings = Settings()
    repo = JsonDocumentRepository()
    embedder = build_embedder(settings.models.embedding_model, settings.models.embedding_dim)
    ingestor = DocumentIngestor(repo, embedder, settings.rag)

    if args.title and len(args.paths) > 1:
        raise SystemExit("--title only makes sense with a single file")

    for path in args.paths:
        source = ingestor.ingest(path, title=args.title)
        print(f"{source.id}  {source.title}  ({source.n_chunks} chunks)  <- {path.name}")

    if args.preview:
        retriever = SimpleRagRetriever(repo, embedder, settings.rag)
        print(f"\n--- top matches for {args.preview!r} ---")
        for rc in retriever.retrieve(args.preview, k=3):
            print(f"[{rc.score:.3f}] {rc.chunk.id} p.{rc.chunk.page}: {rc.chunk.text[:160]}...")
        if settings.models.embedding_model == "hashing":
            print(
                "\nNOTE: using the hashing embedder. These scores reflect word "
                "overlap, not meaning. Set GM_EMBEDDING_MODEL to a real model "
                "before drawing any conclusion from them."
            )


if __name__ == "__main__":
    main()
