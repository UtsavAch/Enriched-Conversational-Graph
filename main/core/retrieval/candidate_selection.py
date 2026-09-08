"""Choosing which prior nodes an extraction call is allowed to see.

This module implements one of the two mechanisms that keep per-turn cost bounded
(thesis section 3.3). The other is deferring memory maintenance to after the
answer is returned.

The intuition: edge classification is inherently quadratic - a new turn could
relate to any of the N prior turns, and asking about all of them costs O(N) per
turn and O(N^2) per conversation. Capping the candidate set at K makes it O(K)
per turn and O(NK) overall, i.e. linear. The price is recall: a genuine relation
to turn 3 is invisible at turn 200 if turn 3 is not in the top-K.

That trade-off is deliberate and is the honest limitation to state in the
thesis. Do not silently raise K to make a number look better without reporting
the cost change.

Three candidate sources (section 5.7 / 5.5 of the Phase 1-2 report):
    1. Recency — guarantees the immediately prior turns are always present.
    2. Semantic — top-K by cosine similarity to the new turn's embedding.
    3. Entity-anchored — prior turns that mention the same named entities,
       taken by recency up to k_entity. This catches "Have you thought it
       through?" style turns where lexical similarity is near zero.
"""

from __future__ import annotations

from dataclasses import dataclass

from core.config import ContextProfile
from core.llm.embeddings import top_k_by_similarity
from core.schema.conversation import ConversationGraph
from core.schema.interaction import InteractionNode


@dataclass
class Candidate:
    """A prior interaction offered to an edge classifier, with its score."""

    node: InteractionNode
    score: float
    reason: str  # 'semantic' | 'recent' | 'entity'

    def render(self, granularity: str = "summary") -> str:
        return self.node.render(granularity)


def select_edge_candidates(
    graph: ConversationGraph,
    new_node: InteractionNode,
    profile: ContextProfile,
    *,
    include_recent: int = 2,
) -> list[Candidate]:
    """Pick the prior turns W2/W3 will be asked about.

    Strategy: recency guarantee + semantic top-K + entity-anchored top-K.

    The recency guarantee exists because of a specific failure the pure-semantic
    version has: a turn like "Have you thought it through?" carries almost no
    lexical content and embeds nowhere near the turn it is responding to. Yet it
    stands in a *resolves* relation to it. Semantic similarity cannot find that;
    adjacency can. Interaction N_7 in the worked example is exactly this case.

    Entity-anchored selection catches a different failure: turns that share
    named entities but different phrasing. These are often structurally linked
    (depends_on, references) even when semantically distant.

    Only turns strictly before ``new_node`` are considered - the graph is built
    incrementally, and letting a classifier see the future would invalidate the
    whole evaluation.
    """
    prior = graph.interactions_before(new_node.turn_index)
    if not prior:
        return []

    chosen: dict[str, Candidate] = {}

    # 1. Recency guarantee.
    for node in prior[-include_recent:] if include_recent else []:
        chosen[node.id] = Candidate(node=node, score=1.0, reason="recent")

    # 2. Semantic top-K over the remainder.
    if new_node.embedding is not None:
        pool = [(n.id, n.embedding) for n in prior if n.id not in chosen]
        by_id = {n.id: n for n in prior}
        budget = max(0, profile.k_semantic - len(chosen))
        for node_id, score in top_k_by_similarity(new_node.embedding, pool, budget):
            chosen[node_id] = Candidate(node=by_id[node_id], score=score, reason="semantic")

    # 3. Entity-anchored: turns that mention the same entities, by recency.
    if profile.k_entity and new_node.named_entities:
        by_id = by_id if "by_id" in dir() else {n.id: n for n in prior}
        entity_budget = max(0, profile.k_entity)
        entity_candidates: dict[str, InteractionNode] = {}
        for eid in new_node.named_entities:
            ent = graph.entities.get(eid)
            if ent is None:
                continue
            for nid in ent.mentioned_in:
                if nid != new_node.id and nid in by_id and nid not in chosen:
                    entity_candidates[nid] = by_id[nid]
        by_recency = sorted(
            entity_candidates.values(), key=lambda n: n.turn_index, reverse=True
        )
        for node in by_recency[:entity_budget]:
            chosen[node.id] = Candidate(node=node, score=0.8, reason="entity")

    return sorted(chosen.values(), key=lambda c: c.node.turn_index)


def render_candidates(candidates: list[Candidate], granularity: str = "summary") -> str:
    """Format a candidate list for a prompt.

    Uses the ``summary`` tier by default: an edge classifier needs to know what
    each candidate established, not its exact wording, and summaries let more
    candidates fit in the same prompt. Falls back to full text automatically
    when W5 has not produced a summary (see ``InteractionNode.render``).
    """
    if not candidates:
        return "(no earlier turns)"
    return "\n".join(f"- {c.render(granularity)}" for c in candidates)
