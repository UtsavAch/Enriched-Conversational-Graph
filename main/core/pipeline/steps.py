"""The five extraction steps, W1-W5.

Kept in one module rather than five files because each is ~40 lines and they
share every import. Splitting them would be structure for its own sake. If any
one grows a real implementation (a merge policy, a validation cascade), split
that one out then.

Call map (Phase 2, section 5.1):

    EMBED  question+answer -> vector          (not an LLM call; see orchestrator)
    W1     entities + speech act              sync, needed by W2/W3 candidates
    W2     hierarchical edges                 async, needs EMBED + W1
    W3     pragmatic edges                    async, needs EMBED + W1
    W4     state node create/update/relate    async
    W5     summary + reference                async
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


# ---------------------------------------------------------------------------
# Steps
# ---------------------------------------------------------------------------


class W1EntityAndSpeechAct(ExtractionStep):
    """Extract named entities and classify the speech act."""

    prompt_name = "w1_extraction"
    step_id = "W1"
    max_tokens = 512

    def build_inputs(self, *, question: str, answer: str, **_: Any) -> dict[str, Any]:
        return {"question": question, "answer": answer}

    def parse(self, payload: Any, **_: Any) -> W1Result:
        entities = []
        for item in payload.get("named_entities", []) or []:
            name = (item.get("name") or "").strip()
            if not name:
                continue
            # Unknown types map to OTHER rather than failing the whole call:
            # losing one entity's precise type is much cheaper than losing the
            # turn's entire entity list to a single bad label.
            try:
                etype = EntityType(item.get("type", "other"))
            except ValueError:
                etype = EntityType.OTHER
            entities.append(ExtractedEntity(name=name, type=etype))

        raw_act = payload.get("speech_act", "information")
        try:
            act = SpeechAct(raw_act)
        except ValueError:
            act = SpeechAct.INFORMATION
        return W1Result(entities=entities, speech_act=act)


class _EdgeStep(ExtractionStep):
    """Shared logic for the two edge classifiers."""

    relation_enum: Any = None
    edge_cls: Any = None
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
        edges = []
        for item in payload.get("edges", []) or []:
            target = item.get("target")
            relation = item.get("relation")
            if relation in (None, "no_relation"):
                continue
            # Reject targets that were not in the candidate list. Models
            # occasionally invent plausible-looking ids; a hallucinated edge is
            # worse than a missing one because it corrupts traversal silently.
            if target not in valid_targets:
                continue
            try:
                edges.append(self.edge_cls(target=target, relation=self.relation_enum(relation)))
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
    Phase 3. That risk is the main argument for the multi-call design - this task
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
                f"- {sn.id} [{sn.type.value}, {sn.status.value}]: {sn.label}"
                for sn in open_state_nodes
            )
        else:
            rendered = "(none yet)"
        return {"question": question, "answer": answer, "open_state_nodes": rendered}

    def parse(self, payload: Any, *, open_state_nodes: list[StateNode], **_: Any) -> W4Result:
        known = {sn.id: sn for sn in open_state_nodes}
        result = W4Result()

        for item in payload.get("creates", []) or []:
            label = (item.get("label") or "").strip()
            if not label:
                continue
            try:
                result.creates.append(
                    StateNodeCreate(
                        state_type=StateNodeType(item.get("state_type")), label=label
                    )
                )
            except ValueError:
                continue

        for item in payload.get("updates", []) or []:
            sid = item.get("state_node_id")
            # Guard against the failure the prompt warns about: models sometimes
            # put an interaction id (N_2, picked up from a [N_2] citation marker)
            # where a state node id belongs.
            if sid not in known:
                continue
            try:
                status = StateNodeStatus(item.get("new_status"))
            except ValueError:
                continue
            # Validate the status is legal for this node's type before accepting
            # it, so an impossible state never reaches storage.
            from core.schema.enums import VALID_STATUSES_BY_TYPE  # noqa: PLC0415

            if status in VALID_STATUSES_BY_TYPE[known[sid].type]:
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
