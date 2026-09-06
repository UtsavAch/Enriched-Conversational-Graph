"""JSON-file implementations of the repository interfaces.

Layout on disk::

    data/conversations/{conversation_id}/
        meta.json          ConversationMeta, incl. schema_version
        interactions.json  {"N_1": {...}, ...}
        entities.json      {"E_1": {...}, ...}
        state_nodes.json   {"SN_1": {...}, ...}

    data/documents/
        sources.json                  {"DOC_1": {...}, ...}
        chunks/DOC_1.json             [ {...}, ... ]

Split into several small files rather than one big one so that a human can open
``state_nodes.json`` and read it, and so that a diff during Phase 3 validation
shows what actually changed. Embeddings live inline; if that becomes unwieldy,
moving them to a sidecar ``.npy`` is a change confined to this file.

Writes are atomic (write to a temp file, then ``os.replace``) so an interrupted
run cannot leave a half-written JSON that fails to parse on next load.
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
