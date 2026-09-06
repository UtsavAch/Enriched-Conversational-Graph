"""The conversation aggregate: everything the memory holds for one dialogue.

This is the object that gets loaded, mutated by the pipeline, and saved. Keeping
it as one explicit aggregate (rather than three loose dicts passed around) means
invariants - ids are unique, edges point at nodes that exist - have exactly one
place to live.
"""

from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel, Field

from core.schema.entity import Entity
from core.schema.interaction import InteractionNode
from core.schema.state_node import StateNode


class ConversationMeta(BaseModel):
    """Bookkeeping written alongside every conversation.

    ``schema_version`` is not optional bureaucracy. The Phase 1 schema will
    change again during Phase 3 validation (the report lists several open items
    that could force it). Without a version stamp, old and new JSON files become
    silently incompatible and nothing tells you which reader to use.
    """

    conversation_id: str
    schema_version: str
    title: str | None = None
    source: str | None = Field(
        None, description="Where this conversation came from: corpus name, 'live', ..."
    )
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    updated_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    tags: list[str] = Field(default_factory=list)


class ConversationGraph(BaseModel):
    """All three node layers for one conversation, plus its metadata.

    Interactions, entities and state nodes are dicts keyed by id rather than
    lists, because every access pattern in the codebase is a lookup by id. The
    on-disk JSON uses the same shape, so loading is a parse, not a rebuild.
    """

    meta: ConversationMeta
    interactions: dict[str, InteractionNode] = Field(default_factory=dict)
    entities: dict[str, Entity] = Field(default_factory=dict)
    state_nodes: dict[str, StateNode] = Field(default_factory=dict)

    # --- ordered access -------------------------------------------------------
    def ordered_interactions(self) -> list[InteractionNode]:
        """Interactions in turn order. The canonical iteration order."""
        return sorted(self.interactions.values(), key=lambda n: n.turn_index)

    def interactions_before(self, turn_index: int) -> list[InteractionNode]:
        """Every interaction strictly earlier than ``turn_index``.

        The graph is built *incrementally*: when processing turn k, only turns
        0..k-1 may be seen. This mirrors what a deployed agent would actually
        have in memory and is what makes evaluation honest. Use this rather than
        iterating all interactions.
        """
        return [n for n in self.ordered_interactions() if n.turn_index < turn_index]

    def open_state_nodes(self) -> list[StateNode]:
        """State nodes worth offering to W4 as merge candidates."""
        return [sn for sn in self.state_nodes.values() if sn.is_open]

    # --- id allocation --------------------------------------------------------
    def next_id(self, prefix: str) -> str:
        """Allocate the next sequential id for a given prefix.

        Sequential integer ids (N_1, N_2, ...) rather than UUIDs, because they
        appear verbatim in prompts and in the visualisation, where readability
        matters more than global uniqueness. Uniqueness is only ever needed
        within one conversation.
        """
        pools = {"N": self.interactions, "E": self.entities, "SN": self.state_nodes}
        if prefix not in pools:
            raise ValueError(f"unknown id prefix '{prefix}'")
        existing = pools[prefix]
        used = []
        for key in existing:
            head, _, tail = key.rpartition("_")
            if head == prefix and tail.isdigit():
                used.append(int(tail))
        return f"{prefix}_{max(used) + 1 if used else 1}"

    # --- integrity ------------------------------------------------------------
    def dangling_references(self) -> list[str]:
        """Every edge or link pointing at an id that does not exist.

        Cheap integrity check. Worth running after a batch ingest and in tests:
        best-effort extraction means a failed LLM call can leave a node
        referencing a target that was never created, and a dangling edge breaks
        graph traversal in ways that are annoying to debug from the symptom.
        """
        problems: list[str] = []
        for node in self.interactions.values():
            for target in node.all_edge_targets():
                if target not in self.interactions:
                    problems.append(f"{node.id}: edge -> missing interaction '{target}'")
            for eid in node.named_entities:
                if eid not in self.entities:
                    problems.append(f"{node.id}: mentions missing entity '{eid}'")
            links = node.state_node_links
            snids = (
                list(links.creates)
                + [s for s, _ in links.updates]
                + [s for s, _ in links.relates]
            )
            for sid in snids:
                if sid not in self.state_nodes:
                    problems.append(f"{node.id}: link -> missing state node '{sid}'")
        for sn in self.state_nodes.values():
            if sn.creation_turn not in self.interactions:
                problems.append(
                    f"{sn.id}: creation_turn -> missing interaction '{sn.creation_turn}'"
                )
        return problems

    def touch(self) -> None:
        """Mark the conversation as modified. Called by the repository on save."""
        self.meta.updated_at = datetime.now(timezone.utc).isoformat()
