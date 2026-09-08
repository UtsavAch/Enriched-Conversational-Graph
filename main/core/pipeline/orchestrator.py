"""The turn pipeline: question in, updated graph out.

This is where the whole system meets. Sequence for one turn:

    1. assemble context      (recency + semantic + graph + state + documents)
    2. generate the answer   (R2)
    3. create the node stub
    4. run extraction        (three-wave concurrent; see below)
    5. apply results to the graph, commit

Steps 1-3 are on the user's critical path. Step 4 runs three waves of
concurrent calls per section 5.7 of the Phase 1-2 report:

    Wave 1: EMBED + W1 + W5 start immediately (need only the raw turn).
    Wave 2: W4 starts as soon as EMBED completes.
    Wave 3: W2 + W3 start once both EMBED and W1 have completed.

Wall-clock cost is the slowest wave, not the sum of all calls. This is one
of the two mechanisms keeping per-turn cost bounded (thesis section 3.3).

Turn serialisation note: the design assumes the next turn cannot start
until this turn's answer and graph write are both complete. Nothing here
enforces that. It holds trivially for batch ingestion (single-threaded)
but not for a live app with concurrent users. Flagged in the Phase 2 report
as an open item.
"""

from __future__ import annotations

import concurrent.futures
import logging
import threading
from dataclasses import dataclass, field
from typing import Any

from core.config import PipelineConfig, Settings
from core.llm.client import LLMClient, LLMError
from core.llm.embeddings import Embedder
from core.llm.prompts import PromptLibrary, prompts as default_prompts
from core.pipeline.base import CallCost, TurnCost
from core.pipeline.steps import (
    CombinedExtraction,
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
from core.schema.enums import (
    DEFAULT_STATUS_BY_TYPE,
    QUESTION_SPEECH_ACTS,
    EpistemicStatus,
    PragmaticRelation,
)
from core.schema.interaction import EpistemicEvent, InteractionNode

logger = logging.getLogger(__name__)


#: Labels that can change a target node's epistemic_status. depends_on and
#: references are absent: they have no status effect. Section 3.5.
EPISTEMIC_TRIGGER_LABELS: frozenset[str] = frozenset({"revises", "resolves", "contradicts"})


def resolve_new_status(current: EpistemicStatus, label: str) -> EpistemicStatus:
    """Implement section 3.5's state-dependent epistemic-status transition table.

    revises always supersedes, regardless of current status.
    superseded is terminal: resolves and contradicts cannot change it.
    resolves clears open or contested alike.
    contradicts sets contested from any non-superseded status.
    """
    if label == "revises":
        return EpistemicStatus.SUPERSEDED
    if current == EpistemicStatus.SUPERSEDED:
        return EpistemicStatus.SUPERSEDED
    if label == "resolves":
        return EpistemicStatus.RESOLVED
    if label == "contradicts":
        return EpistemicStatus.CONTESTED
    return current


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

        cfg: PipelineConfig = self.settings.pipeline
        self.w1 = W1EntityAndSpeechAct(client, cfg, self.library)
        self.w2 = W2HierarchicalEdges(client, cfg, self.library)
        self.w3 = W3PragmaticEdges(client, cfg, self.library)
        self.w4 = W4StateNodes(client, cfg, self.library)
        self.w5 = W5Compression(client, cfg, self.library)
        self.combined = CombinedExtraction(client, cfg, self.library)
        self.assembler = assembler or ContextAssembler(embedder)

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

        # 3. Node stub (embedding is Wave 1 of extraction below) -------------
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
        node.citations = self._extract_citations(answer, graph)

        if not extract:
            node.embedding = self.embedder.embed([node.text_for_embedding()])[0]
            graph.interactions[node.id] = node
            return TurnResult(node=node, context=context, cost=cost, errors=errors)

        # 4-5. Extraction ----------------------------------------------------
        if self.settings.pipeline.strategy == "combined_call":
            self._run_combined_extraction(graph, node, cost, errors)
        else:
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
        """Three-wave concurrent extraction. Section 5.7 of the Phase 1-2 report.

        Wave 1: EMBED + W1 + W5 fire immediately; each needs only the raw turn.
        Wave 2: W4 fires as soon as EMBED completes.
        Wave 3: W2 + W3 fire once both EMBED and W1 have completed; they then
                run in parallel with each other.

        All graph writes are serialised through a single lock so the graph
        never sees a partial update from a concurrent wave.
        """
        lock = threading.Lock()
        embed_done = threading.Event()
        w1_done = threading.Event()

        kw = {"question": node.question, "answer": node.answer}

        # ---- Wave 1 --------------------------------------------------------

        def embed_task() -> None:
            node.embedding = self.embedder.embed([node.text_for_embedding()])[0]
            embed_done.set()

        def w1_task() -> None:
            r = self.w1.run(**kw)
            with lock:
                cost.calls.append(r.cost)
                if r.ok:
                    node.speech_act = r.data.speech_act
                    node.named_entities = self._merge_entities(graph, node, r.data.entities)
                else:
                    errors.append(f"W1: {r.error}")
                node.epistemic_status = (
                    EpistemicStatus.OPEN
                    if node.speech_act in QUESTION_SPEECH_ACTS
                    else EpistemicStatus.RESOLVED
                )
                node.epistemic_history = [
                    EpistemicEvent(
                        caused_by=node.id, trigger="creation", status=node.epistemic_status
                    )
                ]
            w1_done.set()

        def w5_task() -> None:
            r = self.w5.run(**kw)
            with lock:
                cost.calls.append(r.cost)
                if r.ok:
                    node.summary = r.data.summary or None
                    node.reference = r.data.reference or None
                else:
                    errors.append(f"W5: {r.error}")

        # ---- Wave 2 --------------------------------------------------------

        def w4_task() -> None:
            embed_done.wait()
            open_state = graph.open_state_nodes()
            r = self.w4.run(open_state_nodes=open_state, **kw)
            with lock:
                cost.calls.append(r.cost)
                if r.ok:
                    self._apply_state_nodes(graph, node, r.data)
                else:
                    errors.append(f"W4: {r.error}")

        # ---- Wave 3 --------------------------------------------------------

        def w2_w3_task() -> None:
            embed_done.wait()
            w1_done.wait()
            candidates = select_edge_candidates(graph, node, self.settings.edge_profile)
            if not candidates:
                return

            def inner_w2() -> None:
                r = self.w2.run(candidates=candidates, **kw)
                with lock:
                    cost.calls.append(r.cost)
                    if r.ok:
                        node.hierarchical_edges = r.data
                        for edge in r.data:
                            tgt = graph.interactions.get(edge.target)
                            if tgt is not None:
                                tgt.recurrence_count += 1
                    else:
                        errors.append(f"W2: {r.error}")

            def inner_w3() -> None:
                r = self.w3.run(candidates=candidates, **kw)
                with lock:
                    cost.calls.append(r.cost)
                    if r.ok:
                        node.pragmatic_edges = r.data
                        for edge in r.data:
                            tgt = graph.interactions.get(edge.target)
                            if tgt is not None:
                                tgt.recurrence_count += 1
                    else:
                        errors.append(f"W3: {r.error}")

            with concurrent.futures.ThreadPoolExecutor(max_workers=2) as inner_ex:
                for fut in concurrent.futures.as_completed(
                    [inner_ex.submit(inner_w2), inner_ex.submit(inner_w3)]
                ):
                    try:
                        fut.result()
                    except Exception as exc:
                        with lock:
                            errors.append(f"W2/W3 failed: {exc}")

            with lock:
                self._propagate_epistemic_status(graph, node)

        # ---- Dispatch ------------------------------------------------------

        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as ex:
            wave_futs = [
                ex.submit(embed_task),
                ex.submit(w1_task),
                ex.submit(w5_task),
                ex.submit(w4_task),
                ex.submit(w2_w3_task),
            ]
            for fut in concurrent.futures.as_completed(wave_futs):
                try:
                    fut.result()
                except Exception as exc:
                    with lock:
                        errors.append(f"extraction task failed: {exc}")

    def _run_combined_extraction(
        self,
        graph: ConversationGraph,
        node: InteractionNode,
        cost: TurnCost,
        errors: list[str],
    ) -> None:
        """Single combined call returning all W1-W5 outputs at once.

        The alternative to _run_extraction, selected by strategy="combined_call".
        Section 5.2 of the Phase 1-2 report. Candidate selection requires the
        node embedding, so embedding must precede the LLM call.
        """
        node.embedding = self.embedder.embed([node.text_for_embedding()])[0]
        open_state = graph.open_state_nodes()
        candidates = select_edge_candidates(graph, node, self.settings.edge_profile)

        r = self.combined.run(
            question=node.question,
            answer=node.answer,
            candidates=candidates,
            open_state_nodes=open_state,
        )
        cost.calls.append(r.cost)
        if not r.ok:
            errors.append(f"COMBINED: {r.error}")
            return

        result = r.data

        # Apply W1
        node.speech_act = result.w1.speech_act
        node.named_entities = self._merge_entities(graph, node, result.w1.entities)
        node.epistemic_status = (
            EpistemicStatus.OPEN
            if node.speech_act in QUESTION_SPEECH_ACTS
            else EpistemicStatus.RESOLVED
        )
        node.epistemic_history = [
            EpistemicEvent(caused_by=node.id, trigger="creation", status=node.epistemic_status)
        ]

        # Apply W2
        node.hierarchical_edges = result.hierarchical_edges
        for edge in result.hierarchical_edges:
            tgt = graph.interactions.get(edge.target)
            if tgt is not None:
                tgt.recurrence_count += 1

        # Apply W3
        node.pragmatic_edges = result.pragmatic_edges
        for edge in result.pragmatic_edges:
            tgt = graph.interactions.get(edge.target)
            if tgt is not None:
                tgt.recurrence_count += 1

        # Apply W4
        self._apply_state_nodes(graph, node, result.w4)

        # Apply W5
        node.summary = result.w5.summary or None
        node.reference = result.w5.reference or None

        self._propagate_epistemic_status(graph, node)

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
        """Back-propagate epistemic status via section 3.5's transition table.

        Always appends to epistemic_history for full provenance, even when the
        status did not change. Only writes epistemic_status when it actually
        differs from the current value. superseded is terminal: resolves and
        contradicts cannot change it.
        """
        for edge in node.pragmatic_edges:
            label = edge.relation.value
            if label not in EPISTEMIC_TRIGGER_LABELS:
                continue
            target = graph.interactions.get(edge.target)
            if target is None:
                continue
            new_status = resolve_new_status(target.epistemic_status, label)
            if new_status != target.epistemic_status:
                target.epistemic_status = new_status
            target.epistemic_history.append(
                EpistemicEvent(caused_by=node.id, trigger=label, status=new_status)
            )

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
                status=DEFAULT_STATUS_BY_TYPE[create.state_type],
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
