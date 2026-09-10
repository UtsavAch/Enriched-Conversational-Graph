"""Assembling the context a question gets answered from.

Four sources, each answering a different question about relevance:

* **recency**   - what were we just talking about?
* **semantic**  - what earlier turns sound like this one?
* **graph**     - what is structurally connected to those turns?
* **state**     - what goals/decisions/constraints currently bind?
* **documents** - what does the external material say? (separate budget)

The fixed-budget discipline is inherited from the thesis and is the whole point:
context is a zero-sum resource. Adding a graph entry means removing a dialogue
turn. That displacement is what chapter 4 measured, and it is why this module
reports a per-source breakdown rather than just handing back a blob of text.

CRITICAL: external documents get their OWN budget slice, not a share of the
graph slots. Mixing them would make it impossible to say whether a change in
answer quality came from the graph or from the documents.

Algorithm (section 5.5 of the Phase 1-2 report):

    Step 1. Recency layer (always included first).
    Step 2. Entry-point generation: semantic + entity-anchored + state-anchored.
    Step 3. 1-hop graph expansion with split score pools (hierarchical / pragmatic).
    Step 4. Graph-slot selection: pooled (r_pragmatic=None) or split (r_pragmatic float).
    Step 5. Render at chosen compression tier; bump retrieval_count when requested.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from core.config import (
    HIERARCHICAL_EDGE_STRENGTH,
    PRAGMATIC_EDGE_STRENGTH,
    ContextProfile,
)
from core.graph.graph_store import GraphStore
from core.llm.embeddings import Embedder, cosine_similarity, top_k_by_similarity
from core.retrieval.rag.rag_retriever import RetrievedChunk, SimpleRagRetriever
from core.schema.conversation import ConversationGraph
from core.schema.enums import Granularity, StateNodeType

if TYPE_CHECKING:
    from core.schema.interaction import InteractionNode
    from core.schema.state_node import StateNode


#: Edge label families, used to route scored candidates into the right pool.
#: Section 5.5, step 3, "HIERARCHICAL_EDGE_LABELS / PRAGMATIC_EDGE_LABELS".
_HIERARCHICAL_LABELS: frozenset[str] = frozenset({"subcase", "supercase", "same_level"})
_PRAGMATIC_LABELS: frozenset[str] = frozenset(
    {"revises", "contradicts", "resolves", "depends_on", "references"}
)


@dataclass
class ContextItem:
    """One thing injected into the prompt, tagged with why it is there."""

    node_id: str
    text: str
    source: str  # 'recent' | 'semantic' | 'graph' | 'state' | 'document'
    score: float = 0.0
    granularity: str = Granularity.FULL.value


@dataclass
class AssembledContext:
    """The assembled context plus the accounting the evaluation needs.

    ``retrieved_ids`` is what recall@k is computed over. It deliberately
    excludes state nodes and document chunks, which carry no dialogue
    identifier - the same exclusion the thesis makes, so the metric stays
    comparable.
    """

    recent: list[ContextItem] = field(default_factory=list)
    semantic: list[ContextItem] = field(default_factory=list)
    graph: list[ContextItem] = field(default_factory=list)
    state: list[ContextItem] = field(default_factory=list)
    documents: list[ContextItem] = field(default_factory=list)

    @property
    def all_items(self) -> list[ContextItem]:
        return self.recent + self.semantic + self.graph + self.state + self.documents

    @property
    def retrieved_ids(self) -> set[str]:
        """Interaction ids present in context. For recall@k."""
        return {
            i.node_id
            for i in self.recent + self.semantic + self.graph
        }

    def breakdown(self) -> dict[str, int]:
        """Item counts per source. Log this — it makes displacement visible."""
        return {
            "recent": len(self.recent),
            "semantic": len(self.semantic),
            "graph": len(self.graph),
            "state": len(self.state),
            "documents": len(self.documents),
            "total": len(self.all_items),
        }

    def render_section(self, source: str) -> str:
        items = [i for i in self.all_items if i.source == source]
        return "\n".join(i.text for i in items) if items else "(none)"


class ContextAssembler:
    """Builds an ``AssembledContext`` for one question.

    Stateless with respect to the conversation: pass the graph in. This makes it
    trivially usable from the evaluation harness, which replays conversations,
    and from the app, which serves many conversations from one process.
    """

    def __init__(
        self,
        embedder: Embedder,
        rag: SimpleRagRetriever | None = None,
    ) -> None:
        self.embedder = embedder
        self.rag = rag

    def assemble(
        self,
        graph: ConversationGraph,
        question: str,
        profile: ContextProfile,
        *,
        up_to_turn: int | None = None,
        seed_entity_ids: list[str] | None = None,
    ) -> AssembledContext:
        """Assemble context for ``question``.

        Parameters
        ----------
        up_to_turn:
            Only turns strictly before this index may be used. ``None`` means
            all stored turns. Pass this when replaying a conversation for
            evaluation so the memory is exactly what a deployed agent would have
            had at that point.
        seed_entity_ids:
            Entity ids to use as anchors for entity-anchored retrieval. When
            ``None`` (default), the question text is scanned for entity names
            in the graph as a lightweight substitute.
        """
        ctx = AssembledContext()
        interactions = graph.ordered_interactions()
        if up_to_turn is not None:
            interactions = [n for n in interactions if n.turn_index < up_to_turn]
        if not interactions and self.rag is None:
            return ctx

        query_vec = self.embedder.embed([question])[0]

        # ---- Step 1: Recency layer -------------------------------------------
        recent_nodes = interactions[-profile.n_recent :] if profile.n_recent else []
        excluded: set[str] = {n.id for n in recent_nodes}
        ctx.recent = [
            ContextItem(n.id, n.render(Granularity.FULL.value), "recent", 1.0)
            for n in recent_nodes
        ]
        if profile.count_retrieval:
            for n in recent_nodes:
                n.retrieval_count += 1

        k_historical = profile.k_historical - len(ctx.recent)

        # ---- Short-circuit: pure recency ------------------------------------
        # RECENCY_ONLY_PROFILE sets n_recent == k_historical + n_recent, so
        # k_historical drops to zero here. Skip all graph/semantic work.
        if k_historical <= 0:
            self._add_state_context(ctx, graph, query_vec, profile)
            self._add_document_context(ctx, question, profile, graph.meta.conversation_id)
            return ctx

        by_id: dict[str, InteractionNode] = {n.id: n for n in interactions}

        # ---- Step 2: Entry-point generation ---------------------------------

        # 2a. Semantic entry points
        sem_pool = [(n.id, n.embedding) for n in interactions if n.id not in excluded]
        sem_entries: list[str] = [
            nid for nid, _ in top_k_by_similarity(query_vec, sem_pool, profile.k_semantic)
        ]

        # 2b. Entity-anchored entry points
        if seed_entity_ids is None:
            seed_entity_ids = self._find_seed_entities(graph, question)
        entity_entries: list[str] = self._entity_entry_points(
            graph, seed_entity_ids, excluded, profile.k_entity
        )

        # 2c. State-node-anchored entry points (interaction IDs, not state nodes)
        state_entries: list[str] = self._state_entry_points(
            graph, query_vec, excluded, profile.k_state
        )

        # Union, preserving order: semantic first, then entity, then state.
        entry_points: list[str] = list(
            dict.fromkeys(sem_entries + entity_entries + state_entries)
        )

        # ---- Step 3: 1-hop graph expansion + scoring ------------------------
        # Two score pools: hierarchical and pragmatic. Both use the same formula
        # 0.75*sim + 0.25*edge_strength. Kept separate so step 4 can split them
        # across different budget pools when r_pragmatic is set. Section 5.5.
        scored_hierarchical: dict[str, float] = {}
        scored_pragmatic: dict[str, float] = {}

        store = GraphStore(graph)
        for entry in entry_points:
            if entry in by_id:
                node = by_id[entry]
                if node.embedding is not None and entry not in excluded:
                    direct = cosine_similarity(query_vec, node.embedding)
                    scored_hierarchical[entry] = max(
                        scored_hierarchical.get(entry, -1.0), direct
                    )
                    scored_pragmatic[entry] = max(
                        scored_pragmatic.get(entry, -1.0), direct
                    )
            for edge in store.neighbours(entry, groups={"hierarchical", "pragmatic"}):
                nbr_id = edge.target if edge.source == entry else edge.source
                if nbr_id in excluded or nbr_id not in by_id:
                    continue
                nbr = by_id[nbr_id]
                if nbr.embedding is None:
                    continue
                sim = cosine_similarity(query_vec, nbr.embedding)
                score = 0.75 * sim + 0.25 * edge.strength
                if edge.group == "hierarchical":
                    scored_hierarchical[nbr_id] = max(
                        scored_hierarchical.get(nbr_id, -1.0), score
                    )
                else:
                    scored_pragmatic[nbr_id] = max(
                        scored_pragmatic.get(nbr_id, -1.0), score
                    )

        # ---- Step 4: Graph-slot selection -----------------------------------
        g_slots = round(k_historical * profile.graph_slots_fraction)

        if profile.r_pragmatic is None:
            # Production / ENRICHED default: pooled best-edge-wins.
            pooled: dict[str, float] = {}
            for nid in set(scored_hierarchical) | set(scored_pragmatic):
                pooled[nid] = max(
                    scored_hierarchical.get(nid, -1.0),
                    scored_pragmatic.get(nid, -1.0),
                )
            graph_slot_ids = [
                nid for nid, _ in sorted(pooled.items(), key=lambda x: x[1], reverse=True)
            ][:g_slots]
        else:
            # Split budget for ablation comparison (Task 4.4).
            g_pragmatic = round(g_slots * profile.r_pragmatic)
            g_hierarchical = g_slots - g_pragmatic

            h_ranked = sorted(scored_hierarchical.items(), key=lambda x: x[1], reverse=True)
            h_ids = [nid for nid, _ in h_ranked][:g_hierarchical]

            p_ranked = sorted(scored_pragmatic.items(), key=lambda x: x[1], reverse=True)
            p_ids = [
                nid for nid, _ in p_ranked if nid not in h_ids
            ][:g_pragmatic]

            graph_slot_ids = h_ids + p_ids

        # ---- Step 5: Semantic fill of remaining historical budget -----------
        semantic_budget = max(0, k_historical - len(graph_slot_ids))
        graph_id_set = set(graph_slot_ids)
        sem_fill_pool = [
            (n.id, n.embedding)
            for n in interactions
            if n.id not in excluded and n.id not in graph_id_set
        ]
        semantic_ids: list[str] = [
            nid for nid, _ in top_k_by_similarity(query_vec, sem_fill_pool, semantic_budget)
        ]

        # ---- Render semantic slots ------------------------------------------
        for nid in semantic_ids:
            node = by_id.get(nid)
            if node is None:
                continue
            text = node.render(Granularity.FULL.value)
            ctx.semantic.append(ContextItem(nid, text, "semantic", 1.0))
            if profile.count_retrieval:
                node.retrieval_count += 1

        # ---- Render graph slots --------------------------------------------
        for nid in graph_slot_ids:
            node = by_id.get(nid)
            if node is None:
                continue
            tier = Granularity.SUMMARY.value if profile.compress else Granularity.FULL.value
            text = node.render(tier)
            ctx.graph.append(ContextItem(nid, text, "graph", 1.0, tier))
            if profile.count_retrieval:
                node.retrieval_count += 1

        # ---- State context --------------------------------------------------
        self._add_state_context(ctx, graph, query_vec, profile)

        # ---- External documents (separate budget) ---------------------------
        self._add_document_context(ctx, question, profile, graph.meta.conversation_id)

        return ctx

    # -- helpers --------------------------------------------------------------

    def _find_seed_entities(self, graph: ConversationGraph, question: str) -> list[str]:
        """Lightweight entity lookup: exact case-insensitive name match in question.

        Called during answer-generation context assembly, before W1 has run on
        the new turn. Not a model call — just checks whether any known entity
        name appears in the question text.
        """
        q_lower = question.lower()
        return [
            eid
            for eid, ent in graph.entities.items()
            if ent.normalised_name() in q_lower
        ]

    def _entity_entry_points(
        self,
        graph: ConversationGraph,
        entity_ids: list[str],
        excluded: set[str],
        k_entity: int,
    ) -> list[str]:
        """Collect interaction IDs from entity mention lists, take k_entity by recency."""
        if not k_entity or not entity_ids:
            return []
        candidates: dict[str, int] = {}
        for eid in entity_ids:
            ent = graph.entities.get(eid)
            if ent is None:
                continue
            for nid in ent.mentioned_in:
                if nid not in excluded:
                    node = graph.interactions.get(nid)
                    if node is not None:
                        candidates[nid] = node.turn_index
        by_recency = sorted(candidates.items(), key=lambda x: x[1], reverse=True)
        return [nid for nid, _ in by_recency[:k_entity]]

    def _state_entry_points(
        self,
        graph: ConversationGraph,
        query_vec: list[float],
        excluded: set[str],
        k_state: int,
    ) -> list[str]:
        """Find interaction IDs anchored by relevant open state nodes.

        open_question state nodes bypass the similarity gate (they are always
        included up to the k_state budget regardless of score), because an
        unresolved question is relevant to every new turn. Section 5.5.
        """
        if not k_state:
            return []

        open_nodes: list[StateNode] = [
            sn for sn in graph.state_nodes.values() if sn.is_open
        ]
        if not open_nodes:
            return []

        open_q: list[StateNode] = [
            sn for sn in open_nodes if sn.type == StateNodeType.OPEN_QUESTION
        ]
        other: list[StateNode] = [
            sn for sn in open_nodes if sn.type != StateNodeType.OPEN_QUESTION
        ]

        # Score non-open-question nodes by similarity; open questions bypass gate.
        scored: list[tuple[StateNode, float]] = [
            (sn, 1.0) for sn in open_q
        ]
        if other:
            other_pool = [(sn.id, sn.embedding) for sn in other if sn.embedding is not None]
            sn_by_id = {sn.id: sn for sn in other}
            for sn_id, score in top_k_by_similarity(query_vec, other_pool, k_state):
                scored.append((sn_by_id[sn_id], score))

        scored.sort(key=lambda x: x[1], reverse=True)
        top_sns: list[StateNode] = [sn for sn, _ in scored[:k_state]]

        interaction_ids: set[str] = set()
        for sn in top_sns:
            interaction_ids.add(sn.creation_turn)
            for u in sn.updates:
                interaction_ids.add(u.turn)
            for r in sn.relations:
                interaction_ids.add(r.turn)
        return list(interaction_ids - excluded)

    def _add_state_context(
        self,
        ctx: AssembledContext,
        graph: ConversationGraph,
        query_vec: list[float],
        profile: ContextProfile,
    ) -> None:
        """Inject open state nodes directly (as project-state context, not graph slots)."""
        state_pool = [
            (sn.id, sn.embedding) for sn in graph.state_nodes.values() if sn.is_open
        ]
        if not state_pool or not profile.k_state:
            return
        for sn_id, score in top_k_by_similarity(query_vec, state_pool, profile.k_state):
            sn = graph.state_nodes[sn_id]
            ctx.state.append(
                ContextItem(
                    sn_id,
                    f"[{sn_id}] {sn.type.value}: {sn.label} (status: {sn.status.value})",
                    "state",
                    score,
                    Granularity.REFERENCE.value,
                )
            )

    def _add_document_context(
        self,
        ctx: AssembledContext,
        question: str,
        profile: ContextProfile,
        conversation_id: str,
    ) -> None:
        """Retrieve document chunks, scoped to what this conversation actually
        references (uploaded or explicitly selected - see
        ``get_conversation_document_ids``).

        A conversation with no references at all falls back to searching the
        whole global corpus - this is what keeps old, batch-ingested
        conversations (never wired to any particular document) working
        unchanged. Once a conversation has at least one reference, retrieval
        is scoped strictly to that set, which is both the relevance fix (no
        unrelated PDF wins a slot on a coincidental match) and, since
        ``SimpleRagRetriever`` filters before scoring, a real reduction in how
        many chunks get cosine-scored per query.
        """
        if self.rag is None or not profile.k_documents:
            return
        from core.persistence.json_repository import (  # noqa: PLC0415
            get_conversation_document_ids,
        )

        source_ids = get_conversation_document_ids(conversation_id) or None
        chunks: list[RetrievedChunk] = self.rag.retrieve(
            question, k=profile.k_documents, source_ids=source_ids
        )
        ctx.documents = [
            ContextItem(rc.chunk.id, rc.render(), "document", rc.score)
            for rc in chunks
        ]
