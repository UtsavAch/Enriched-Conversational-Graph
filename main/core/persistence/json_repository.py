"""JSON-file implementations of the repository interfaces.

Layout on disk::

    data/conversations/{conversation_id}/
        meta.json          ConversationMeta, incl. schema_version
        interactions.json  {"N_1": {...}, ...}
        entities.json      {"E_1": {...}, ...}
        state_nodes.json   {"SN_1": {...}, ...}
        conversation.json  [ {"id", "timestamp", "turns": [...]}, ... ] - derived,
                            see ``_conversation_export``
        documents/          only present once a document has been attached to
            manifest.json    this conversation - see ``attach_document_to_conversation``
            {DOC_id}_{filename}

    data/documents/
        sources.json                  {"DOC_1": {...}, ...}
        chunks/DOC_1.json             [ {...}, ... ]

Split into several small files rather than one big one so that a human can open
``state_nodes.json`` and read it, and so that a diff during Phase 3 validation
shows what actually changed. Embeddings live inline; if that becomes unwieldy,
moving them to a sidecar ``.npy`` is a change confined to this file.

Writes are atomic (write to a temp file, then ``os.replace``) so an interrupted
run cannot leave a half-written JSON that fails to parse on next load.

``data/documents/`` remains the single source of truth for retrieval (chunks +
embeddings, possibly shared across conversations) - see the design note in
``core/schema/document.py``. The per-conversation ``documents/`` folder is a
separate, purely archival copy so a conversation directory is self-contained.
"""

from __future__ import annotations

import json
import os
import shutil
import tempfile
from pathlib import Path
from typing import Any

from core.config import CONVERSATIONS_DIR, DOCUMENTS_DIR
from core.schema import SCHEMA_VERSION
from core.schema.conversation import ConversationGraph, ConversationMeta
from core.schema.document import DocumentChunk, DocumentSource
from core.schema.entity import Entity
from core.schema.interaction import InteractionNode
from core.schema.state_node import StateNode


def _atomic_write_json(path: Path, payload: Any) -> None:
    """Write JSON such that the file is either the old content or the new one."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2, ensure_ascii=False)
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def _read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


def _conversation_export(graph: ConversationGraph) -> list[dict[str, Any]]:
    """Render ``graph`` in the raw ingest-input shape (see ``worked_example/``).

    Purely a read view over ``interactions`` - the InteractionNode is the
    source of truth for question/answer text, so this is regenerated on every
    save and can never drift out of sync with ``interactions.json``.
    """
    return [
        {
            "id": node.id,
            "timestamp": node.timestamp,
            "turns": [
                {"speaker": "user", "text": node.question},
                {"speaker": "assistant", "text": node.answer},
            ],
        }
        for node in graph.ordered_interactions()
    ]


def _conversation_docs_dir(conversation_id: str, root: Path | str) -> Path:
    if "/" in conversation_id or conversation_id.startswith("."):
        raise ValueError(f"unsafe conversation id: {conversation_id!r}")
    return Path(root) / conversation_id / "documents"


def _write_conversation_document_entry(
    docs_dir: Path, source: DocumentSource, filename: str | None
) -> None:
    manifest_path = docs_dir / "manifest.json"
    manifest = _read_json(manifest_path, {})
    manifest[source.id] = {
        "id": source.id,
        "title": source.title,
        "source_type": source.source_type,
        "filename": filename,
        "n_chunks": source.n_chunks,
        "ingested_at": source.ingested_at,
    }
    _atomic_write_json(manifest_path, manifest)


def attach_document_to_conversation(
    conversation_id: str,
    path: Path,
    source: DocumentSource,
    root: Path | str = CONVERSATIONS_DIR,
) -> Path:
    """Copy an ingested file into ``conversation_id``'s ``documents/`` folder.

    Used when a document is freshly uploaded *through* a conversation - the
    file itself is still around to copy. For an already-ingested document
    being added to a conversation without re-uploading, see
    ``reference_document_in_conversation``.

    Archival only: ``data/documents/`` (chunks + embeddings) stays the sole
    store retrieval reads from - this just makes the conversation directory
    self-contained by keeping a copy of what actually grounded it, alongside a
    small manifest. Re-attaching the same source overwrites its manifest entry
    and re-copies the file. The manifest doubles as the record of which
    documents this conversation's retrieval is scoped to - see
    ``get_conversation_document_ids``.
    """
    path = Path(path)
    docs_dir = _conversation_docs_dir(conversation_id, root)
    docs_dir.mkdir(parents=True, exist_ok=True)

    # Use source.title rather than path.name: for an API upload, path is a
    # temp file with a random name (e.g. "tmpXY9f2a.pdf"), while source.title
    # is the human-readable original filename stem.
    safe_title = source.title.replace("/", "_").strip() or source.id
    dest = docs_dir / f"{source.id}_{safe_title}{path.suffix}"
    shutil.copy2(path, dest)

    _write_conversation_document_entry(docs_dir, source, dest.name)
    return dest


def reference_document_in_conversation(
    conversation_id: str,
    source: DocumentSource,
    root: Path | str = CONVERSATIONS_DIR,
) -> None:
    """Scope an already-ingested global document to this conversation, without
    copying a file - there may not even be one available locally any more.

    This is the "select an existing document" path: the document was ingested
    once (via upload or the CLI) and now a *different* conversation wants its
    retrieval scoped to include it too. Retrieval treats this identically to
    an uploaded-and-attached document - both just add an id to the manifest
    that ``get_conversation_document_ids`` reads.
    """
    docs_dir = _conversation_docs_dir(conversation_id, root)
    docs_dir.mkdir(parents=True, exist_ok=True)
    _write_conversation_document_entry(docs_dir, source, filename=None)


def unreference_document_in_conversation(
    conversation_id: str,
    source_id: str,
    root: Path | str = CONVERSATIONS_DIR,
) -> None:
    """Remove a document's reference from a conversation (uploaded or selected).

    Deletes the archived copy too, if this conversation has one - a selected
    (not uploaded) reference has no local copy, so there is nothing beyond the
    manifest entry to remove. Does nothing if the conversation never
    referenced this document (no manifest, or no matching entry).
    """
    docs_dir = _conversation_docs_dir(conversation_id, root)
    manifest_path = docs_dir / "manifest.json"
    manifest = _read_json(manifest_path, {})
    entry = manifest.pop(source_id, None)
    if entry is None:
        return
    if entry.get("filename"):
        (docs_dir / entry["filename"]).unlink(missing_ok=True)
    _atomic_write_json(manifest_path, manifest)


def get_conversation_document_ids(
    conversation_id: str,
    root: Path | str = CONVERSATIONS_DIR,
) -> list[str]:
    """Every document id (uploaded or selected) currently referenced by this
    conversation. Empty if the conversation has never attached or selected
    any - callers should treat that as "no explicit scope", not "no documents
    exist". Used to scope RAG retrieval - see
    ``ContextAssembler._add_document_context``.
    """
    docs_dir = _conversation_docs_dir(conversation_id, root)
    manifest = _read_json(docs_dir / "manifest.json", {})
    return list(manifest.keys())


class JsonConversationRepository:
    """Conversation storage backed by a directory of JSON files."""

    def __init__(self, root: Path | str = CONVERSATIONS_DIR) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    # --- paths ---------------------------------------------------------------
    def _dir(self, conversation_id: str) -> Path:
        if "/" in conversation_id or conversation_id.startswith("."):
            raise ValueError(f"unsafe conversation id: {conversation_id!r}")
        return self.root / conversation_id

    # --- interface -----------------------------------------------------------
    def list_conversations(self) -> list[str]:
        return sorted(
            p.name for p in self.root.iterdir() if p.is_dir() and (p / "meta.json").exists()
        )

    def exists(self, conversation_id: str) -> bool:
        return (self._dir(conversation_id) / "meta.json").exists()

    def load(self, conversation_id: str) -> ConversationGraph:
        d = self._dir(conversation_id)
        if not (d / "meta.json").exists():
            raise KeyError(f"no conversation '{conversation_id}' under {self.root}")

        meta = ConversationMeta.model_validate(_read_json(d / "meta.json", {}))
        self._check_schema_version(meta)

        interactions = {
            k: InteractionNode.model_validate(v)
            for k, v in _read_json(d / "interactions.json", {}).items()
        }
        entities = {
            k: Entity.model_validate(v)
            for k, v in _read_json(d / "entities.json", {}).items()
        }
        state_nodes = {
            k: StateNode.model_validate(v)
            for k, v in _read_json(d / "state_nodes.json", {}).items()
        }
        return ConversationGraph(
            meta=meta,
            interactions=interactions,
            entities=entities,
            state_nodes=state_nodes,
        )

    def save(self, graph: ConversationGraph) -> None:
        graph.touch()
        d = self._dir(graph.meta.conversation_id)
        _atomic_write_json(d / "meta.json", graph.meta.model_dump(mode="json"))
        _atomic_write_json(
            d / "interactions.json",
            {k: v.model_dump(mode="json") for k, v in graph.interactions.items()},
        )
        _atomic_write_json(
            d / "entities.json",
            {k: v.model_dump(mode="json") for k, v in graph.entities.items()},
        )
        _atomic_write_json(
            d / "state_nodes.json",
            {k: v.model_dump(mode="json") for k, v in graph.state_nodes.items()},
        )
        _atomic_write_json(d / "conversation.json", _conversation_export(graph))

    def delete(self, conversation_id: str) -> None:
        shutil.rmtree(self._dir(conversation_id), ignore_errors=True)

    def create(
        self, conversation_id: str, title: str | None = None, source: str | None = None
    ) -> ConversationGraph:
        """Create and persist an empty conversation. Convenience, not interface."""
        graph = ConversationGraph(
            meta=ConversationMeta(
                conversation_id=conversation_id,
                schema_version=SCHEMA_VERSION,
                title=title,
                source=source,
            )
        )
        self.save(graph)
        return graph

    # --- versioning ----------------------------------------------------------
    @staticmethod
    def _check_schema_version(meta: ConversationMeta) -> None:
        """Warn loudly on a version mismatch rather than failing mysteriously later.

        Deliberately a warning, not an exception: during Phase 3 you will want
        to load older data to see what changed. When a real breaking migration
        happens, add the migration to ``core/persistence/README.md`` and turn
        this into a hard failure for versions below the cutoff.
        """
        if meta.schema_version != SCHEMA_VERSION:
            import warnings

            warnings.warn(
                f"conversation '{meta.conversation_id}' was written with schema "
                f"version {meta.schema_version}, current is {SCHEMA_VERSION}. "
                "Fields may be missing or reinterpreted.",
                stacklevel=2,
            )


class JsonDocumentRepository:
    """Document storage backed by JSON files under ``data/documents``."""

    def __init__(self, root: Path | str = DOCUMENTS_DIR) -> None:
        self.root = Path(root)
        self.chunks_dir = self.root / "chunks"
        self.chunks_dir.mkdir(parents=True, exist_ok=True)
        self.sources_path = self.root / "sources.json"

    def _load_sources(self) -> dict[str, dict]:
        return _read_json(self.sources_path, {})

    def list_sources(self) -> list[DocumentSource]:
        return [DocumentSource.model_validate(v) for v in self._load_sources().values()]

    def get_source(self, source_id: str) -> DocumentSource:
        sources = self._load_sources()
        if source_id not in sources:
            raise KeyError(f"no document source '{source_id}'")
        return DocumentSource.model_validate(sources[source_id])

    def add_source(self, source: DocumentSource, chunks: list[DocumentChunk]) -> None:
        # Chunks first: if this process dies between the two writes, we are left
        # with orphaned chunks (harmless, invisible) rather than a source that
        # claims chunks which do not exist (breaks retrieval).
        _atomic_write_json(
            self.chunks_dir / f"{source.id}.json",
            [c.model_dump(mode="json") for c in chunks],
        )
        sources = self._load_sources()
        source.n_chunks = len(chunks)
        sources[source.id] = source.model_dump(mode="json")
        _atomic_write_json(self.sources_path, sources)

    def get_chunks(self, source_id: str) -> list[DocumentChunk]:
        raw = _read_json(self.chunks_dir / f"{source_id}.json", [])
        return [DocumentChunk.model_validate(c) for c in raw]

    def all_chunks(self) -> list[DocumentChunk]:
        out: list[DocumentChunk] = []
        for source_id in self._load_sources():
            out.extend(self.get_chunks(source_id))
        return out

    def delete_source(self, source_id: str) -> None:
        (self.chunks_dir / f"{source_id}.json").unlink(missing_ok=True)
        sources = self._load_sources()
        sources.pop(source_id, None)
        _atomic_write_json(self.sources_path, sources)

    def next_source_id(self) -> str:
        used = [
            int(k.split("_")[1])
            for k in self._load_sources()
            if k.startswith("DOC_") and k.split("_")[1].isdigit()
        ]
        return f"DOC_{max(used) + 1 if used else 1}"
