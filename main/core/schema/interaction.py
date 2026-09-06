"""Interaction nodes: one question/answer pair, the unit of the memory graph.

This is the schema's centre of gravity. The thesis' defining choice is node
*granularity*: one node = one complete interaction (user query + the response
produced for it).
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, field_validator

from core.schema.enums import (
    EpistemicStatus,
    HierarchicalRelation,
    PragmaticRelation,
    SpeechAct,
    StateNodeStatus,
    StateRelation,
)


class HierarchicalEdge(BaseModel):
    """A topic-structure edge to another interaction node. Produced by W2."""

    target: str = Field(..., description="Interaction node id, e.g. 'N_2'.")
    relation: HierarchicalRelation

    model_config = {"frozen": True}


class PragmaticEdge(BaseModel):
    """A discourse-relation edge to another interaction node. Produced by W3."""

    target: str = Field(..., description="Interaction node id, e.g. 'N_2'.")
    relation: PragmaticRelation

    model_config = {"frozen": True}


class StateNodeLinks(BaseModel):
    """Everything this interaction did to the state-node layer. Produced by W4.

    Three distinct actions, deliberately kept separate because they mean
    different things:

    * ``creates``  - this turn brought a new goal/decision/constraint/question
      into existence.
    * ``updates``  - this turn changed an existing state node's lifecycle status
      (e.g. an open question became ``resolved``).
    * ``relates``  - this turn stands in some relation to a state node without
      necessarily changing it (supports, contradicts, is constrained by...).

    A single turn can do all three. See interaction N_8 in the worked example,
    which both ``updates`` SN_4 to resolved and ``relates`` to it via resolves.
    """

    creates: list[str] = Field(default_factory=list, description="New SN ids.")
    updates: list[tuple[str, StateNodeStatus]] = Field(
        default_factory=list, description="(state_node_id, new_status) pairs."
    )
    relates: list[tuple[str, StateRelation]] = Field(
        default_factory=list, description="(state_node_id, relation) pairs."
    )


class EpistemicEvent(BaseModel):
    """One entry in a node's epistemic audit trail.

    Recording *why* a status changed - and which turn caused it - is what lets
    the visualisation explain a ``superseded`` node instead of just marking it.
    """

    caused_by: str = Field(..., description="Interaction node id, or self on creation.")
    trigger: str = Field(
        ...,
        description="'creation', or the pragmatic relation that caused the change.",
    )
    status: EpistemicStatus

    model_config = {"frozen": True}


class InteractionNode(BaseModel):
    """One question/answer pair plus everything extracted from it.

    Field provenance (which pipeline call produces what) is noted per field, so
    that when an extraction call is changed you can see immediately which parts
    of the node are affected.
    """

    # --- identity and content -------------------------------------------------
    id: str = Field(..., description="Stable id, convention 'N_<n>'.")
    conversation_id: str
    turn_index: int = Field(..., ge=0, description="0-based position in the conversation.")
    date: str | None = Field(None, description="ISO date, if the corpus provides one.")

    question: str = Field(..., description="The user's turn. Not model-produced.")
    answer: str = Field(..., description="The assistant's turn. Produced by R2.")

    # --- retrieval ------------------------------------------------------------
    embedding: list[float] | None = Field(
        None,
        description="Embedding of (question + answer). Produced by EMBED. "
        "Nullable so a node can be persisted before embedding completes.",
    )

    # --- extracted attributes -------------------------------------------------
    named_entities: list[str] = Field(
        default_factory=list, description="Entity ids (E_n) mentioned here. From W1."
    )
    speech_act: SpeechAct = Field(
        SpeechAct.INFORMATION, description="Discourse function. From W1."
    )
    citations: list[str] = Field(
        default_factory=list,
        description="Interaction ids the answer-generation call actually cited.",
    )

    # --- epistemic state ------------------------------------------------------
    epistemic_status: EpistemicStatus = EpistemicStatus.RESOLVED
    epistemic_history: list[EpistemicEvent] = Field(default_factory=list)

    # --- compression tiers (W5) ----------------------------------------------
    summary: str | None = Field(None, description="One-sentence form. From W5.")
    reference: str | None = Field(None, description="Few-word form. From W5.")

    # --- edges ----------------------------------------------------------------
    hierarchical_edges: list[HierarchicalEdge] = Field(default_factory=list)
    pragmatic_edges: list[PragmaticEdge] = Field(default_factory=list)
    state_node_links: StateNodeLinks = Field(default_factory=StateNodeLinks)

    # --- usage counters -------------------------------------------------------
    # Used by the visualisation for node size, and available as a retrieval
    # signal. Not currently used for ranking - that would be a Phase 4 ablation.
    recurrence_count: int = Field(0, ge=0, description="Times this topic recurred.")
    retrieval_count: int = Field(0, ge=0, description="Times this node was retrieved.")

    # --- grounding (external RAG) --------------------------------------------
    grounded_by: list[str] = Field(
        default_factory=list,
        description="DocumentChunk ids used to ground this answer. Deliberately a "
        "flat provenance list, NOT a typed discourse edge - see the RAG "
        "architecture decision.",
    )

    @field_validator("id")
    @classmethod
    def _id_must_be_nonempty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("InteractionNode.id must be a non-empty string")
        return v

    # --- convenience ----------------------------------------------------------
    def text_for_embedding(self) -> str:
        """The exact string EMBED should encode. Kept here so every caller agrees."""
        return f"{self.question}\n{self.answer}"

    def render(self, granularity: str) -> str:
        """Render this node at a given compression tier for context injection.

        Falls back gracefully: if W5 has not run yet, ``summary`` and
        ``reference`` are ``None``, and we degrade to the fuller form rather
        than injecting an empty string.
        """
        if granularity == "reference" and self.reference:
            return f"[{self.id}] {self.reference}"
        if granularity in ("reference", "summary") and self.summary:
            return f"[{self.id}] {self.summary}"
        return f"[{self.id}] Q: {self.question}\nA: {self.answer}"

    def all_edge_targets(self) -> set[str]:
        """Every interaction node this one points at, regardless of edge type."""
        return {e.target for e in self.hierarchical_edges} | {
            e.target for e in self.pragmatic_edges
        }

    def to_storage_dict(self) -> dict[str, Any]:
        """JSON-ready dict. Enums become plain strings via ``mode='json'``."""
        return self.model_dump(mode="json")
