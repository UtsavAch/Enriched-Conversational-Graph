"""Schema layer: the single source of truth for what the memory graph contains.

Nothing in this package imports from ``core.pipeline``, ``core.persistence`` or
``core.retrieval``. The dependency arrow points one way only, which is what lets
the schema be reused by the evaluation harness and the app without dragging in
LLM clients.

``SCHEMA_VERSION`` is written into every conversation's ``meta.json``. Bump it
whenever a field is added, removed, or changes meaning, and add a note to
``core/persistence/README.md`` describing how to migrate.
"""

SCHEMA_VERSION = "0.3.0"

from core.schema.conversation import ConversationGraph, ConversationMeta  # noqa: E402
from core.schema.document import DocumentChunk, DocumentSource  # noqa: E402
from core.schema.entity import Entity  # noqa: E402
from core.schema.enums import (  # noqa: E402
    EntityType,
    EpistemicStatus,
    Granularity,
    HierarchicalRelation,
    NodeKind,
    PragmaticRelation,
    SpeechAct,
    StateNodeStatus,
    StateNodeType,
    StateRelation,
)
from core.schema.interaction import (  # noqa: E402
    EpistemicEvent,
    HierarchicalEdge,
    InteractionNode,
    PragmaticEdge,
    StateNodeLinks,
)
from core.schema.state_node import StateNode  # noqa: E402

__all__ = [
    "SCHEMA_VERSION",
    "ConversationGraph",
    "ConversationMeta",
    "DocumentChunk",
    "DocumentSource",
    "Entity",
    "EntityType",
    "EpistemicEvent",
    "EpistemicStatus",
    "Granularity",
    "HierarchicalEdge",
    "HierarchicalRelation",
    "InteractionNode",
    "NodeKind",
    "PragmaticEdge",
    "PragmaticRelation",
    "SpeechAct",
    "StateNode",
    "StateNodeLinks",
    "StateNodeStatus",
    "StateNodeType",
    "StateRelation",
]
