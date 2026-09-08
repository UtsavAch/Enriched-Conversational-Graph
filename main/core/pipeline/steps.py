"""The five extraction steps, W1-W5, plus the combined-call variant.

Kept in one module rather than five files because each is ~40 lines and they
share every import. Splitting them would be structure for its own sake. If any
one grows a real implementation (a merge policy, a validation cascade), split
that one out then.

Call map (Phase 2, section 5.1):

    EMBED  question+answer -> vector          (not an LLM call; see orchestrator)
    W1     entities + speech act              sync, needed by W2/W3 candidates
    W2     hierarchical edges                 async, needs EMBED + W1
    W3     pragmatic edges                    async, needs EMBED + W1
    W4     state node create/update/relate    async, needs EMBED (for state candidates)
    W5     summary + reference                async, needs only raw turn

Prompt output formats (section 5.6 of the Phase 1-2 report):
    W1  → {"entities": [...], "speech_act": "..."}
    W2  → {"<candidate_id>": "<label>", ...}   (dict, no_relation included)
    W3  → {"<candidate_id>": "<label>", ...}   (dict, no_relation included)
    W4  → {"creates": [...], "updates": [...], "relates": [...]}
    W5  → {"summary": "...", "reference": "..."}
    combined → all of the above in one object (section 5.6, combined prompt)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from core.pipeline.base import ExtractionStep
from core.retrieval.candidate_selection import Candidate, render_candidates
from core.schema.enums import (
    EntityType,
    HierarchicalRelation,
    PragmaticRelation,
    SpeechAct,
    StateNodeStatus,
    StateNodeType,
    StateRelation,
    TERMINAL_STATUSES_BY_TYPE,
    VALID_STATUSES_BY_TYPE,
)
from core.schema.interaction import HierarchicalEdge, PragmaticEdge
from core.schema.state_node import StateNode


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------


@dataclass
class ExtractedEntity:
    """An entity as W1 reports it: a surface form and a type, no id yet.

    Id assignment happens in the orchestrator, because deciding whether this is
    a new entity or another mention of an existing one requires the whole
    conversation - which a single extraction call does not have.
    """

    name: str
    type: EntityType


@dataclass
class W1Result:
    entities: list[ExtractedEntity] = field(default_factory=list)
    speech_act: SpeechAct = SpeechAct.INFORMATION


@dataclass
class StateNodeCreate:
    state_type: StateNodeType
    label: str


@dataclass
class W4Result:
    creates: list[StateNodeCreate] = field(default_factory=list)
    updates: list[tuple[str, StateNodeStatus]] = field(default_factory=list)
    relates: list[tuple[str, StateRelation]] = field(default_factory=list)


@dataclass
class W5Result:
    summary: str = ""
    reference: str = ""


@dataclass
class CombinedResult:
    """All extraction outputs in one object. Produced by the combined call."""

    w1: W1Result = field(default_factory=W1Result)
    hierarchical_edges: list[HierarchicalEdge] = field(default_factory=list)
    pragmatic_edges: list[PragmaticEdge] = field(default_factory=list)
    w4: W4Result = field(default_factory=W4Result)
    w5: W5Result = field(default_factory=W5Result)


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _parse_entities(payload: Any) -> list[ExtractedEntity]:
    """Parse the ``entities`` list from W1 or combined-call output."""
    entities = []
    for item in payload.get("entities", []) or []:
        name = (item.get("name") or "").strip()
        if not name:
            continue
        try:
            etype = EntityType(item.get("type", "other"))
        except ValueError:
            etype = EntityType.OTHER
        entities.append(ExtractedEntity(name=name, type=etype))
    return entities


def _parse_speech_act(payload: Any) -> SpeechAct:
    raw = payload.get("speech_act", "information")
    try:
        return SpeechAct(raw)
    except ValueError:
        return SpeechAct.INFORMATION


def _parse_edge_dict(
    payload: Any,
    key: str,
    relation_enum: Any,
    edge_cls: Any,
    valid_targets: set[str],
) -> list[Any]:
    """Parse W2/W3 dict-format output: {"<candidate_id>": "<label>", ...}.

    Section 5.6: prompts return a dict keyed by candidate id. no_relation
    entries are present in the dict but are not stored as edges.
    """
    raw = payload.get(key, {}) or {}
    edges = []
    for target, relation_str in raw.items():
        if relation_str in (None, "no_relation"):
            continue
        if target not in valid_targets:
            continue
        try:
            edges.append(edge_cls(target=target, relation=relation_enum(relation_str)))
        except ValueError:
            continue
    return edges


def _parse_w4_result(payload: Any, known: dict[str, StateNode]) -> W4Result:
    """Parse creates/updates/relates from W4 or combined-call output."""
    result = W4Result()

    for item in payload.get("creates", []) or []:
        label = (item.get("label") or "").strip()
        if not label:
            continue
        try:
            result.creates.append(
                StateNodeCreate(state_type=StateNodeType(item.get("state_type")), label=label)
            )
        except ValueError:
            continue

    for item in payload.get("updates", []) or []:
        sid = item.get("state_node_id")
        if sid not in known:
            continue
        try:
            status = StateNodeStatus(item.get("new_status"))
        except ValueError:
            continue
        sn = known[sid]
        if sn.status in TERMINAL_STATUSES_BY_TYPE[sn.type]:
            continue
        if status in VALID_STATUSES_BY_TYPE[sn.type]:
            result.updates.append((sid, status))

    for item in payload.get("relates", []) or []:
        sid = item.get("state_node_id")
        if sid not in known:
            continue
        try:
            result.relates.append((sid, StateRelation(item.get("relation"))))
        except ValueError:
            continue

    return result


# ---------------------------------------------------------------------------
# Steps
# ---------------------------------------------------------------------------


class W1EntityAndSpeechAct(ExtractionStep):
    """Extract named entities and classify the speech act.

    Output key is ``entities`` (not ``named_entities``) — matching section 5.6
    of the Phase 1-2 report.
    """

    prompt_name = "w1_extraction"
    step_id = "W1"
    max_tokens = 512

    def build_inputs(self, *, question: str, answer: str, **_: Any) -> dict[str, Any]:
        return {"question": question, "answer": answer}

    def parse(self, payload: Any, **_: Any) -> W1Result:
        return W1Result(
            entities=_parse_entities(payload),
            speech_act=_parse_speech_act(payload),
        )


class _EdgeStep(ExtractionStep):
    """Shared logic for the two edge classifiers (W2, W3).

    Both return dict format: {"<candidate_id>": "<label>", ...}.
    Section 5.6 of the Phase 1-2 report.
    """

    relation_enum: Any = None
    edge_cls: Any = None
    dict_key: str = ""        # key holding the dict in the JSON response
    max_tokens = 512

    def build_inputs(
        self, *, question: str, answer: str, candidates: list[Candidate], **_: Any
    ) -> dict[str, Any]:
        return {
            "question": question,
            "answer": answer,
            "candidates": render_candidates(candidates),
        }

    def parse(self, payload: Any, *, candidates: list[Candidate], **_: Any) -> list[Any]:
        valid_targets = {c.node.id for c in candidates}
        # The top-level payload IS the dict {"N_1": "subcase", ...}.
        # Models occasionally wrap it; _parse_edge_dict handles both.
        raw = payload if isinstance(payload, dict) else {}
        edges = []
        for target, relation_str in raw.items():
            if relation_str in (None, "no_relation"):
                continue
            if target not in valid_targets:
                continue
            try:
                edges.append(
                    self.edge_cls(target=target, relation=self.relation_enum(relation_str))
                )
            except ValueError:
                continue
        return edges


class W2HierarchicalEdges(_EdgeStep):
    """Classify subcase / supercase / same_level against candidate prior turns."""

    prompt_name = "w2_hierarchical"
    step_id = "W2"
    relation_enum = HierarchicalRelation
    edge_cls = HierarchicalEdge


class W3PragmaticEdges(_EdgeStep):
    """Classify revises / contradicts / resolves / depends_on / references.

    The highest-risk extraction task in the pipeline: five subtle categories that
    a model must distinguish, and the one most likely to need prompt iteration in
    Phase 3. That risk is the main argument for the multi-call design — this task
    gets a whole prompt to itself.
    """

    prompt_name = "w3_pragmatic"
    step_id = "W3"
    relation_enum = PragmaticRelation
    edge_cls = PragmaticEdge


class W4StateNodes(ExtractionStep):
    """Create, update, or relate to goals/decisions/constraints/open questions."""

    prompt_name = "w4_state_nodes"
    step_id = "W4"
    max_tokens = 768

    def build_inputs(
        self, *, question: str, answer: str, open_state_nodes: list[StateNode], **_: Any
    ) -> dict[str, Any]:
        if open_state_nodes:
            rendered = "\n".join(
                f"- {sn.id} ({sn.type.value}): \"{sn.label}\" - {sn.status.value}"
                for sn in open_state_nodes
            )
        else:
            rendered = "(none yet)"
        return {"question": question, "answer": answer, "open_state_nodes": rendered}

    def parse(self, payload: Any, *, open_state_nodes: list[StateNode], **_: Any) -> W4Result:
        known = {sn.id: sn for sn in open_state_nodes}
        return _parse_w4_result(payload, known)


class W5Compression(ExtractionStep):
    """Produce the summary and reference tiers used for compressed injection."""

    prompt_name = "w5_compression"
    step_id = "W5"
    max_tokens = 256

    def build_inputs(self, *, question: str, answer: str, **_: Any) -> dict[str, Any]:
        return {"question": question, "answer": answer}

    def parse(self, payload: Any, **_: Any) -> W5Result:
        return W5Result(
            summary=(payload.get("summary") or "").strip(),
            reference=(payload.get("reference") or "").strip(),
        )


class CombinedExtraction(ExtractionStep):
    """Single combined call producing all W1-W5 outputs at once.

    The alternative to multi_call, compared empirically in Phase 4.
    Section 5.2 and the combined prompt template (section 5.6).
    """

    prompt_name = "combined_extraction"
    step_id = "COMBINED"
    max_tokens = 1024

    def build_inputs(
        self,
        *,
        question: str,
        answer: str,
        candidates: list[Candidate],
        open_state_nodes: list[StateNode],
        **_: Any,
    ) -> dict[str, Any]:
        if open_state_nodes:
            rendered_state = "\n".join(
                f"- {sn.id} ({sn.type.value}): \"{sn.label}\" - {sn.status.value}"
                for sn in open_state_nodes
            )
        else:
            rendered_state = "(none yet)"
        return {
            "question": question,
            "answer": answer,
            "candidates": render_candidates(candidates),
            "open_state_nodes": rendered_state,
        }

    def parse(
        self,
        payload: Any,
        *,
        candidates: list[Candidate],
        open_state_nodes: list[StateNode],
        **_: Any,
    ) -> CombinedResult:
        valid_targets = {c.node.id for c in candidates}
        known = {sn.id: sn for sn in open_state_nodes}

        w1 = W1Result(
            entities=_parse_entities(payload),
            speech_act=_parse_speech_act(payload),
        )

        h_edges = _parse_edge_dict(
            payload, "hierarchical_edges", HierarchicalRelation, HierarchicalEdge, valid_targets
        )
        p_edges = _parse_edge_dict(
            payload, "pragmatic_edges", PragmaticRelation, PragmaticEdge, valid_targets
        )

        w4 = _parse_w4_result(payload, known)

        w5 = W5Result(
            summary=(payload.get("summary") or "").strip(),
            reference=(payload.get("reference") or "").strip(),
        )

        return CombinedResult(
            w1=w1,
            hierarchical_edges=h_edges,
            pragmatic_edges=p_edges,
            w4=w4,
            w5=w5,
        )
