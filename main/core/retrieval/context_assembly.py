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
"""

from __future__ import annotations

from dataclasses import dataclass, field

from core.config import ContextProfile
from core.graph.graph_store import GraphStore
from core.graph.traversal import expand
from core.llm.embeddings import Embedder, top_k_by_similarity
from core.retrieval.rag.rag_retriever import RetrievedChunk, SimpleRagRetriever
from core.schema.conversation import ConversationGraph
from core.schema.enums import Granularity


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
        """Item counts per source. Log this - it is what makes displacement visible."""
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
        use_graph: bool = True,
        use_documents: bool = True,
    ) -> AssembledContext:
        """Assemble context for ``question``.

        Parameters
        ----------
        up_to_turn:
            Only turns strictly before this index may be used. ``None`` means
            all stored turns. Pass this when replaying a conversation for
            evaluation so the memory is exactly what a deployed agent would have
            had at that point.
        use_graph / use_documents:
            Ablation switches. ``use_graph=False`` reproduces the semantic-RAG
            baseline; both False reproduces the recency-only baseline. Having
            these as flags rather than separate builder classes is what makes
            the three-way comparison a controlled test of one variable.
        """
        ctx = AssembledContext()
        interactions = graph.ordered_interactions()
        if up_to_turn is not None:
            interactions = [n for n in interactions if n.turn_index < up_to_turn]
        if not interactions and self.rag is None:
            return ctx

        query_vec = self.embedder.embed([question])[0]

        # --- Layer 1: recency ------------------------------------------------
        recent_nodes = interactions[-profile.n_recent :] if profile.n_recent else []
        recent_ids = {n.id for n in recent_nodes}
        ctx.recent = [
            ContextItem(n.id, n.render(Granularity.FULL.value), "recent", 1.0)
            for n in recent_nodes
        ]

        # --- Layer 2a: semantic ----------------------------------------------
        pool = [(n.id, n.embedding) for n in interactions if n.id not in recent_ids]
        by_id = {n.id: n for n in interactions}
        graph_slots = profile.graph_slots if use_graph else 0
        semantic_budget = max(0, profile.k_historical - len(ctx.recent) - graph_slots)

        seeds: dict[str, float] = {}
        for node_id, score in top_k_by_similarity(query_vec, pool, semantic_budget):
            node = by_id[node_id]
            ctx.semantic.append(
                ContextItem(node_id, node.render(Granularity.FULL.value), "semantic", score)
            )
            if len(seeds) < profile.k_semantic:
                seeds[node_id] = score

        # --- Layer 2b: graph expansion ---------------------------------------
        if use_graph and graph_slots > 0 and seeds:
            store = GraphStore(graph)
            already = recent_ids | {i.node_id for i in ctx.semantic}
            for result in expand(store, seeds, limit=graph_slots, exclude=already):
                node = by_id.get(result.node_id)
                if node is None:
                    continue
                # Graph entries are injected at SUMMARY granularity. This is the
                # compression lever from task 1.4: it directly reduces the
                # displacement cost, since a graph slot now costs a sentence
                # rather than a full Q&A pair.
                ctx.graph.append(
                    ContextItem(
                        node.id,
                        node.render(Granularity.SUMMARY.value),
                        "graph",
                        result.score,
                        Granularity.SUMMARY.value,
                    )
                )

        # --- Layer 3: project state ------------------------------------------
        # Always included when present, and always at reference granularity: a
        # binding constraint is short, and forgetting it is a much worse failure
        # than spending three lines on it.
        state_pool = [
            (sn.id, sn.embedding) for sn in graph.state_nodes.values() if sn.is_open
        ]
        if state_pool and profile.k_state:
            for sn_id, score in top_k_by_similarity(query_vec, state_pool, profile.k_state):
                sn = graph.state_nodes[sn_id]
                ctx.state.append(
                    ContextItem(
                        sn.id,
                        f"[{sn.id}] {sn.type.value}: {sn.label} (status: {sn.status.value})",
                        "state",
                        score,
                        Granularity.REFERENCE.value,
                    )
                )

        # --- External documents (separate budget) ----------------------------
        if use_documents and self.rag is not None and profile.k_documents:
            chunks: list[RetrievedChunk] = self.rag.retrieve(question, k=profile.k_documents)
            ctx.documents = [
                ContextItem(rc.chunk.id, rc.render(), "document", rc.score)
                for rc in chunks
            ]

        return ctx
