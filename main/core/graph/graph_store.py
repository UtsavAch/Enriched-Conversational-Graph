"""An adjacency view over a conversation graph.

``ConversationGraph`` stores edges *on the nodes* (each interaction owns its
outgoing edges), which is the right shape for storage: one node, one JSON
object, no separate edge table to keep in sync. But it is the wrong shape for
traversal, where you constantly need "what points at this node".

``GraphStore`` builds the reverse index once and answers both directions. It is
a derived, throwaway view: build it, traverse, discard. It deliberately holds no
authority - ``ConversationGraph`` remains the single source of truth.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from core.config import (
    HIERARCHICAL_EDGE_STRENGTH,
    PRAGMATIC_EDGE_STRENGTH,
    STATE_RELATION_STRENGTH,
)
from core.schema.conversation import ConversationGraph


@dataclass(frozen=True)
class Edge:
    """A directed, typed, weighted edge in the unified view.

    ``group`` distinguishes edges that live in different layers of the schema
    and should be filterable independently:

    * ``hierarchical`` / ``pragmatic`` - interaction to interaction
    * ``state_link``                   - interaction to state node
    * ``mention``                      - interaction to entity
    * ``citation``                     - interaction to interaction, from the
      answer's explicit ``[N_x]`` markers rather than from a classifier
    """

    source: str
    target: str
    relation: str
    group: str
    strength: float = 1.0


def _strength(group: str, relation: str) -> float:
    """Look up an edge weight. Unknown relations get a neutral 0.5.

    All these weights are provisional (see ``core/config.py``). They are Phase 4
    sweep targets, not findings.
    """
    if group == "hierarchical":
        return HIERARCHICAL_EDGE_STRENGTH.get(relation, 0.5)
    if group == "pragmatic":
        return PRAGMATIC_EDGE_STRENGTH.get(relation, 0.5)
    if group == "state_link":
        return STATE_RELATION_STRENGTH.get(relation, 0.5)
    return 0.3  # mentions and citations: weak by default


class GraphStore:
    """Bidirectional adjacency over one conversation.

    Built in O(V + E) from a ``ConversationGraph``. Rebuild after every mutation
    rather than trying to keep it incrementally in sync - conversations are
    small enough that the rebuild is free, and an incrementally-maintained index
    is a class of bug this project does not need.
    """

    def __init__(self, graph: ConversationGraph) -> None:
        self.graph = graph
        self._out: dict[str, list[Edge]] = defaultdict(list)
        self._in: dict[str, list[Edge]] = defaultdict(list)
        self._edges: list[Edge] = []
        self._build()

    # --- construction --------------------------------------------------------
    def _add(self, edge: Edge) -> None:
        self._edges.append(edge)
        self._out[edge.source].append(edge)
        self._in[edge.target].append(edge)

    def _build(self) -> None:
        for node in self.graph.interactions.values():
            for e in node.hierarchical_edges:
                self._add(
                    Edge(node.id, e.target, e.relation.value, "hierarchical",
                         _strength("hierarchical", e.relation.value))
                )
            for e in node.pragmatic_edges:
                self._add(
                    Edge(node.id, e.target, e.relation.value, "pragmatic",
                         _strength("pragmatic", e.relation.value))
                )
            for eid in node.named_entities:
                self._add(Edge(node.id, eid, "mentions", "mention", _strength("mention", "")))
            for cid in node.citations:
                # Skip citations that duplicate a classified edge - the classified
                # edge carries a relation label and is strictly more informative.
                if cid not in node.all_edge_targets():
                    self._add(Edge(node.id, cid, "cites", "citation", _strength("citation", "")))

            links = node.state_node_links
            for sid in links.creates:
                self._add(Edge(node.id, sid, "creates", "state_link", 1.0))
            for sid, status in links.updates:
                self._add(
                    Edge(node.id, sid, f"updates -> {status}", "state_link", 0.9)
                )
            for sid, relation in links.relates:
                rel = relation.value if hasattr(relation, "value") else str(relation)
                self._add(Edge(node.id, sid, rel, "state_link", _strength("state_link", rel)))

    # --- queries -------------------------------------------------------------
    @property
    def edges(self) -> list[Edge]:
        return list(self._edges)

    def out_edges(self, node_id: str, groups: set[str] | None = None) -> list[Edge]:
        edges = self._out.get(node_id, [])
        return [e for e in edges if groups is None or e.group in groups]

    def in_edges(self, node_id: str, groups: set[str] | None = None) -> list[Edge]:
        edges = self._in.get(node_id, [])
        return [e for e in edges if groups is None or e.group in groups]

    def neighbours(self, node_id: str, groups: set[str] | None = None) -> list[Edge]:
        """All edges touching ``node_id``, in either direction.

        Traversal treats the graph as undirected on purpose. A turn that
        *revises* an earlier one is relevant context for that earlier one, and
        vice versa; following only the stored direction would make relevance
        depend on which turn happened to come first.
        """
        return self.out_edges(node_id, groups) + self.in_edges(node_id, groups)

    def degree(self, node_id: str) -> int:
        return len(self._out.get(node_id, [])) + len(self._in.get(node_id, []))

    def stats(self) -> dict[str, int]:
        """Edge counts by group. Cheap health check for a built graph.

        Worth watching during Phase 3: the thesis found ``supercase`` fired in
        only 4 of 3,954 edges on LoCoMo. If a relation type is near-zero on your
        validation corpus too, that is a finding about either the corpus or the
        prompt, and you want to notice it early.
        """
        counts: dict[str, int] = defaultdict(int)
        for e in self._edges:
            counts[e.group] += 1
            counts[f"{e.group}:{e.relation}"] += 1
        counts["nodes:interaction"] = len(self.graph.interactions)
        counts["nodes:entity"] = len(self.graph.entities)
        counts["nodes:state"] = len(self.graph.state_nodes)
        return dict(counts)
