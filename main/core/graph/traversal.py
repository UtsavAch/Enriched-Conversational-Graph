"""Graph expansion: turning entry-point nodes into a ranked set of neighbours.

This is the retrieval-side mechanism the thesis measures. The intuition: pure
semantic similarity finds turns that *sound like* the query; graph expansion
additionally pulls in turns that are *structurally related* to those - the turn
that revised them, the question they answered, the decision they depend on.

The scoring is deliberately simple and explainable:

    score(neighbour) = seed_score x edge_strength x decay^(hops - 1)

One multiplicative chain, no learned weights. Every term is inspectable, which
matters when you have to explain in a thesis why a particular node was
retrieved. Anything learned would need its own training data and its own
validation, and would confound the question being asked.
"""

from __future__ import annotations

from dataclasses import dataclass

from core.graph.graph_store import GraphStore

#: Per-hop attenuation. [provisional] - a Phase 4 sweep target, not a finding.
DEFAULT_HOP_DECAY = 0.6

#: Edge groups followed during expansion. Mentions and citations are excluded by
#: default: entity co-mention is a very weak relevance signal and tends to pull
#: in everything that mentions a common entity, crowding out stronger evidence.
#: Including them is a legitimate ablation - pass ``groups`` explicitly.
DEFAULT_GROUPS = frozenset({"hierarchical", "pragmatic"})


@dataclass
class ExpansionResult:
    """One node reached by expansion, with enough provenance to explain it."""

    node_id: str
    score: float
    hops: int
    via: str = ""       # the relation label of the last edge traversed
    from_seed: str = ""  # which entry point this was reached from

    def explain(self) -> str:
        return (
            f"{self.node_id} (score={self.score:.3f}, {self.hops} hop(s) "
            f"from {self.from_seed} via '{self.via}')"
        )


def expand(
    store: GraphStore,
    seeds: dict[str, float],
    *,
    max_hops: int = 2,
    limit: int = 10,
    hop_decay: float = DEFAULT_HOP_DECAY,
    groups: frozenset[str] = DEFAULT_GROUPS,
    exclude: set[str] | None = None,
) -> list[ExpansionResult]:
    """Breadth-first expansion from scored entry points.

    Parameters
    ----------
    seeds:
        ``{node_id: similarity_score}`` - typically the top-k semantic matches.
        Their scores propagate, so expanding from a strong match yields stronger
        neighbours than expanding from a weak one.
    max_hops:
        How far to walk. 2 is the sensible default: 1 hop is the direct
        discourse neighbourhood, 2 catches "the turn that resolved the question
        that this turn raised". Beyond 2 the scores are attenuated to noise and
        the candidate set explodes.
    limit:
        Cap on results returned. Corresponds to the graph slots in the context
        budget.
    exclude:
        Node ids already in context (the seeds themselves, the recency layer).
        Excluded rather than deduplicated afterwards, so they do not consume
        expansion budget.

    Returns
    -------
    Results sorted by score, highest first. A node reachable by several paths
    keeps its best score - not the sum, which would reward densely-connected
    hubs simply for being hubs.
    """
    exclude = set(exclude or ()) | set(seeds)
    best: dict[str, ExpansionResult] = {}

    # frontier entries: (node_id, accumulated_score, hops, seed_id)
    frontier: list[tuple[str, float, int, str]] = [
        (nid, score, 0, nid) for nid, score in seeds.items()
    ]
    visited: set[str] = set(seeds)

    while frontier:
        node_id, score, hops, seed = frontier.pop(0)
        if hops >= max_hops:
            continue
        for edge in store.neighbours(node_id, groups=set(groups)):
            other = edge.target if edge.source == node_id else edge.source
            if other in exclude:
                continue
            new_score = score * edge.strength * (hop_decay**hops)
            result = ExpansionResult(
                node_id=other,
                score=new_score,
                hops=hops + 1,
                via=edge.relation,
                from_seed=seed,
            )
            if other not in best or new_score > best[other].score:
                best[other] = result
            if other not in visited:
                visited.add(other)
                frontier.append((other, new_score, hops + 1, seed))

    ranked = sorted(best.values(), key=lambda r: r.score, reverse=True)
    return ranked[:limit]


def connected_component(store: GraphStore, node_id: str, groups: frozenset[str] = DEFAULT_GROUPS) -> set[str]:
    """Every node reachable from ``node_id``. Diagnostic, not used in retrieval.

    Useful during Phase 3 validation: a graph that fragments into many small
    components is a sign the edge classifier is emitting ``no_relation`` too
    freely, which is exactly the thinness problem the thesis observed.
    """
    seen = {node_id}
    stack = [node_id]
    while stack:
        current = stack.pop()
        for edge in store.neighbours(current, groups=set(groups)):
            other = edge.target if edge.source == current else edge.source
            if other not in seen:
                seen.add(other)
                stack.append(other)
    return seen
