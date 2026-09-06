"""The turn pipeline: question in, updated graph out.

This is where the whole system meets. Sequence for one turn:

    1. assemble context      (recency + semantic + graph + state + documents)
    2. generate the answer   (R2)
    3. create the node, embed it                     (EMBED)
    4. select edge candidates                        (R1)
    5. run extraction                                (W1-W5)
    6. apply results to the graph, commit

Steps 1-3 are on the user's critical path. Steps 4-6 are memory maintenance and
are deferred until after the answer is returned - that deferral is one of the
two mechanisms keeping per-turn cost bounded (thesis section 3.3).

TWO KNOWN GAPS, both stated rather than hidden:

* **Concurrency.** The design says W2/W3/W4/W5 fire concurrently, so wall-clock
  cost is the slowest call, not their sum. This implementation runs them
  *sequentially*. That is a deliberate first step - correctness before latency -
  but it means the latency figures in the Phase 2 report are not yet met by the
  code. ``AsyncTurnPipeline`` is the intended fix; see the note at the bottom.
* **Turn serialisation.** The design assumes the next turn cannot start until
  this turn's graph write completes. Nothing here enforces that. It holds
  trivially for batch ingestion (single-threaded) but not for a live app with
  concurrent users. Flagged in the Phase 2 report as an open item.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from core.config import PipelineConfig, Settings
from core.llm.client import LLMClient, LLMError
from core.llm.embeddings import Embedder
from core.llm.prompts import PromptLibrary, prompts as default_prompts
from core.pipeline.base import CallCost, TurnCost
from core.pipeline.steps import (
    ExtractedEntity,
    W1EntityAndSpeechAct,
    W2HierarchicalEdges,
    W3PragmaticEdges,
    W4StateNodes,
    W5Compression,
)
from core.retrieval.candidate_selection import select_edge_candidates
from core.retrieval.context_assembly import AssembledContext, ContextAssembler
from core.schema.conversation import ConversationGraph
from core.schema.entity import Entity
from core.schema.enums import QUESTION_SPEECH_ACTS, EpistemicStatus, PragmaticRelation
from core.schema.interaction import EpistemicEvent, InteractionNode

logger = logging.getLogger(__name__)


#: Which pragmatic relation, arriving at a node, changes that node's status.
#: Kept as data rather than an if-chain so the policy is visible in one place
#: and an ablation can swap it out.
STATUS_EFFECT: dict[PragmaticRelation, EpistemicStatus] = {
    PragmaticRelation.REVISES: EpistemicStatus.SUPERSEDED,
    PragmaticRelation.CONTRADICTS: EpistemicStatus.CONTESTED,
    PragmaticRelation.RESOLVES: EpistemicStatus.RESOLVED,
}


@dataclass
class TurnResult:
    """Everything one processed turn produced. Returned for logging and the app."""

    node: InteractionNode
    context: AssembledContext
    cost: TurnCost
    errors: list[str] = field(default_factory=list)

    def summary(self) -> dict[str, Any]:
        return {
            "node_id": self.node.id,
            "speech_act": self.node.speech_act.value,
            "n_hierarchical": len(self.node.hierarchical_edges),
            "n_pragmatic": len(self.node.pragmatic_edges),
            "n_entities": len(self.node.named_entities),
            "n_state_created": len(self.node.state_node_links.creates),
            "context": self.context.breakdown(),
            "cost": self.cost.summary(),
            "errors": self.errors,
        }


class TurnPipeline:
    """Processes one turn end to end against a ``ConversationGraph``.

    Mutates the graph in memory. Persisting is the caller's job - which keeps
    the pipeline usable in the evaluation harness, where you replay a
    conversation many times and never want to write.
    """

    def __init__(
        self,
        client: LLMClient,
        embedder: Embedder,
        settings: Settings | None = None,
        library: PromptLibrary | None = None,
        assembler: ContextAssembler | None = None,
    ) -> None:
        self.settings = settings or Settings()
        self.client = client
        self.embedder = embedder
        self.library = library or default_prompts
        self.assembler = assembler or ContextAssembler(embedder)

        cfg: PipelineConfig = self.settings.pipeline
        self.w1 = W1EntityAndSpeechAct(client, cfg, self.library)
        self.w2 = W2HierarchicalEdges(client, cfg, self.library)
        self.w3 = W3PragmaticEdges(client, cfg, self.library)
        self.w4 = W4StateNodes(client, cfg, self.library)
        self.w5 = W5Compression(client, cfg, self.library)

    # -- public API ----------------------------------------------------------

    def process_turn(
        self,
        graph: ConversationGraph,
        question: str,
        *,
        answer: str | None = None,
        date: str | None = None,
        extract: bool = True,
    ) -> TurnResult:
        """Add one turn to ``graph``.

        Parameters
        ----------
        answer:
            Supply this when ingesting an existing conversation, to skip answer
            generation. Leave ``None`` for live use, where the pipeline
            generates the answer from assembled context.
        extract:
            ``False`` runs only steps 1-3, producing a node with an embedding
            and no structure. Useful as a null baseline and for fast smoke tests.
        """
        cost = TurnCost(turn_id="")
        errors: list[str] = []
        turn_index = len(graph.interactions)

        # 1. Context ---------------------------------------------------------
        context = self.assembler.assemble(
            graph, question, self.settings.answer_profile, up_to_turn=turn_index
        )

        # 2. Answer ----------------------------------------------------------
        if answer is None:
            answer, gen_cost = self._generate_answer(question, context)
            cost.calls.append(gen_cost)

        # 3. Node + embedding ------------------------------------------------
        node = InteractionNode(
            id=graph.next_id("N"),
            conversation_id=graph.meta.conversation_id,
            turn_index=turn_index,
            date=date,
            question=question,
            answer=answer,
            grounded_by=[i.node_id for i in context.documents],
        )
        cost.turn_id = node.id
        node.embedding = self.embedder.embed([node.text_for_embedding()])[0]
        node.citations = self._extract_citations(answer, graph)

        if not extract:
            graph.interactions[node.id] = node
            return TurnResult(node=node, context=context, cost=cost, errors=errors)

        # 4-5. Extraction ----------------------------------------------------
        self._run_extraction(graph, node, cost, errors)

        # 6. Commit ----------------------------------------------------------
        graph.interactions[node.id] = node
        return TurnResult(node=node, context=context, cost=cost, errors=errors)

    # -- internals -----------------------------------------------------------

    def _generate_answer(self, question: str, context: AssembledContext) -> tuple[str, CallCost]:
        system, user = self.library.render(
            "answer_generation",
            question=question,
            state_context=context.render_section("state"),
            memory_context="\n".join(
                i.text for i in context.semantic + context.graph
            ) or "(none)",
            document_context=context.render_section("document"),
            recent_context=context.render_section("recent"),
        )
        try:
            response = self.client.complete(
                system=system,
                user=user,
                max_tokens=1024,
                temperature=self.settings.pipeline.answer_temperature,
            )
        except LLMError as exc:
            logger.error("answer generation failed: %s", exc)
            return ("", CallCost(step="R2", failed=True))
        return (
            response.text,
            CallCost(
                step="R2",
                input_tokens=response.input_tokens,
                output_tokens=response.output_tokens,
                latency_s=response.latency_s,
            ),
        )

    def _run_extraction(
        self,
        graph: ConversationGraph,
        node: InteractionNode,
        cost: TurnCost,
        errors: list[str],
    ) -> None:
        """Run W1-W5 and fold their results into the node and the graph.

        Ordering here reflects the *data* dependencies, not an assumption that
        order matters for correctness elsewhere: W1 must finish before W2/W3
        because candidate selection needs the node's embedding and W1's entity
        list. W2 and W3 have no dependency on each other (confirmed by testing;
        see the worked example, N_8) and could run in parallel.
        """
        kwargs = {"question": node.question, "answer": node.answer}

        # W1
        r1 = self.w1.run(**kwargs)
        cost.calls.append(r1.cost)
        if r1.ok:
            node.speech_act = r1.data.speech_act
            node.named_entities = self._merge_entities(graph, node, r1.data.entities)
        else:
            errors.append(f"W1: {r1.error}")

        node.epistemic_status = (
            EpistemicStatus.OPEN
            if node.speech_act in QUESTION_SPEECH_ACTS
            else EpistemicStatus.RESOLVED
        )
        node.epistemic_history = [
            EpistemicEvent(caused_by=node.id, trigger="creation", status=node.epistemic_status)
        ]

        # R1: candidate selection (no model call)
        candidates = select_edge_candidates(graph, node, self.settings.edge_profile)

        # W2 / W3 - independent of each other
        if candidates:
            r2 = self.w2.run(candidates=candidates, **kwargs)
            cost.calls.append(r2.cost)
            if r2.ok:
                node.hierarchical_edges = r2.data
            else:
                errors.append(f"W2: {r2.error}")

            r3 = self.w3.run(candidates=candidates, **kwargs)
            cost.calls.append(r3.cost)
            if r3.ok:
                node.pragmatic_edges = r3.data
                self._propagate_epistemic_status(graph, node)
            else:
                errors.append(f"W3: {r3.error}")

        # W4
        open_state = graph.open_state_nodes()
        r4 = self.w4.run(open_state_nodes=open_state, **kwargs)
        cost.calls.append(r4.cost)
        if r4.ok:
            self._apply_state_nodes(graph, node, r4.data)
        else:
            errors.append(f"W4: {r4.error}")

        # W5
        r5 = self.w5.run(**kwargs)
        cost.calls.append(r5.cost)
        if r5.ok:
            node.summary = r5.data.summary or None
            node.reference = r5.data.reference or None
        else:
            errors.append(f"W5: {r5.error}")

    def _merge_entities(
        self, graph: ConversationGraph, node: InteractionNode, extracted: list[ExtractedEntity]
    ) -> list[str]:
        """Attach entity ids to the node, creating entities only when new.

        Matching is exact on the normalised surface form. This will miss "the
        advisor" vs "my thesis advisor" and is a known, measurable limitation -
        precision/recall of entity extraction is a Phase 3 validation metric, and
        under-merging will show up there. Resist the urge to add fuzzy matching
        before you have that measurement; you would be tuning blind.
        """
        by_name = {e.normalised_name(): e for e in graph.entities.values()}
        ids: list[str] = []
        for item in extracted:
            key = item.name.strip().lower()
            existing = by_name.get(key)
            if existing is None:
                entity = Entity(
                    id=graph.next_id("E"),
                    conversation_id=graph.meta.conversation_id,
                    type=item.type,
                    name=item.name,
                    mentioned_in=[node.id],
                )
                graph.entities[entity.id] = entity
                by_name[key] = entity
                ids.append(entity.id)
            else:
                if node.id not in existing.mentioned_in:
                    existing.mentioned_in.append(node.id)
                ids.append(existing.id)
        return ids

    def _propagate_epistemic_status(
        self, graph: ConversationGraph, node: InteractionNode
    ) -> None:
        """Update earlier nodes' status based on this turn's pragmatic edges.

        This is what makes the memory *self-correcting*: when a turn revises an
        earlier decision, the earlier node is marked superseded, so retrieval can
        tell the agent "this used to be true". Without it, the graph accumulates
        stale claims with nothing marking them stale.
        """
        for edge in node.pragmatic_edges:
            effect = STATUS_EFFECT.get(edge.relation)
            target = graph.interactions.get(edge.target)
            if effect is None or target is None:
                continue
            target.epistemic_status = effect
            target.epistemic_history.append(
                EpistemicEvent(
                    caused_by=node.id, trigger=edge.relation.value, status=effect
                )
            )
            target.recurrence_count += 1

    def _apply_state_nodes(
        self, graph: ConversationGraph, node: InteractionNode, result: Any
    ) -> None:
        from core.schema.state_node import StateNode  # noqa: PLC0415

        for create in result.creates:
            sn = StateNode(
                id=graph.next_id("SN"),
                conversation_id=graph.meta.conversation_id,
                type=create.state_type,
                label=create.label,
                creation_turn=node.id,
            )
            sn.embedding = self.embedder.embed([sn.label])[0]
            graph.state_nodes[sn.id] = sn
            node.state_node_links.creates.append(sn.id)

        for sid, status in result.updates:
            sn = graph.state_nodes.get(sid)
            if sn is None:
                continue
            try:
                sn.apply_update(node.id, status)
            except ValueError as exc:
                logger.warning("rejected state update: %s", exc)
                continue
            node.state_node_links.updates.append((sid, status))

        for sid, relation in result.relates:
            sn = graph.state_nodes.get(sid)
            if sn is None:
                continue
            sn.apply_relation(node.id, relation)
            node.state_node_links.relates.append((sid, relation))

    @staticmethod
    def _extract_citations(answer: str, graph: ConversationGraph) -> list[str]:
        """Pull ``[N_x]`` markers out of a generated answer.

        Only markers naming a node that actually exists are kept, so a
        hallucinated citation does not create a dangling edge.
        """
        import re  # noqa: PLC0415

        found = re.findall(r"\[(N_\d+)\]", answer or "")
        return [cid for cid in dict.fromkeys(found) if cid in graph.interactions]


# ---------------------------------------------------------------------------
# Not implemented yet, on purpose
# ---------------------------------------------------------------------------
#
# ``AsyncTurnPipeline`` - the concurrent variant. W2, W3, W4 and W5 have no data
# dependency on one another, so they can be fired together with asyncio.gather,
# making wall-clock cost the slowest call rather than the sum of five.
#
# It is deliberately NOT written yet, for a research reason: the Phase 2 latency
# estimates *assume* genuine concurrency, and the report flags that assumption as
# unverified. Writing the async version before measuring the sequential one would
# mean never having the baseline number that shows concurrency mattered. Measure
# first (``scripts/ingest_conversation.py`` reports per-turn cost), then optimise.
