"""Every enum here corresponds directly to a field. Keeping them as enums rather than
free strings means an LLM extraction call that hallucinates a label fails loudly
at parse time instead of silently polluting the graph.

If you add a value here you are changing the schema. Bump ``SCHEMA_VERSION`` in
``core/schema/__init__.py`` when you do.

Exception: entity types are NOT a fixed enum (see ``DEFAULT_ENTITY_TYPES`` below
and ``core/schema/entity.py``). The Phase 1-2 report (section 3.2) is explicit
that the entity-type list is domain-specific, not fixed - a REST API corpus
needs ``resource``/``endpoint``, a different domain needs something else. Adding
or changing entity types is a per-conversation config change (``ConversationMeta
.entity_type_vocab``, see ``evaluation_report.md`` section 8), not a schema
version bump.
"""

from __future__ import annotations

from enum import Enum


class StrEnum(str, Enum):
    """String-valued enum so instances serialise to plain JSON strings."""

    def __str__(self) -> str:  # pragma: no cover - trivial
        return str(self.value)


class NodeKind(StrEnum):
    """The three (plus one) kinds of node the memory can hold.

    ``DOCUMENT_CHUNK`` is deliberately a *separate kind*, not a variant of
    ``INTERACTION``.
    """

    INTERACTION = "interaction"
    ENTITY = "entity"
    STATE = "state"
    DOCUMENT_CHUNK = "document_chunk"


class SpeechAct(StrEnum):
    """Discourse function of a turn. Produced by extraction call W1."""

    FACTUAL_QUESTION = "factual_question"
    CLARIFICATION_REQUEST = "clarification_request"
    DECISION = "decision"
    SUGGESTION = "suggestion"
    FEEDBACK = "feedback"
    CORRECTION = "correction"
    FOLLOW_UP = "follow_up"
    AGREEMENT = "agreement"
    DISAGREEMENT = "disagreement"
    INFORMATION = "information"
    REQUEST = "request"


#: Speech acts that default a new interaction node to ``EpistemicStatus.OPEN``.
QUESTION_SPEECH_ACTS = frozenset(
    {SpeechAct.FACTUAL_QUESTION, SpeechAct.CLARIFICATION_REQUEST}
)


class EpistemicStatus(StrEnum):
    """
    Whether what an interaction node asserts still stands.
    """

    OPEN = "open"
    RESOLVED = "resolved"
    CONTESTED = "contested"
    SUPERSEDED = "superseded"


class HierarchicalRelation(StrEnum):
    """
    Topic-structure relations. Labels describe the NEW turn relative to the CANDIDATE.
    subcase: NEW is more specific. supercase: NEW is more general. same_level: parallel.
    """

    SUBCASE = "subcase"
    SUPERCASE = "supercase"
    SAME_LEVEL = "same_level"


class PragmaticRelation(StrEnum):
    """
    Pragmatic relations — what the new turn DOES to the earlier one.
    """

    REVISES = "revises"
    CONTRADICTS = "contradicts"
    RESOLVES = "resolves"
    DEPENDS_ON = "depends_on"
    REFERENCES = "references"


class StateNodeType(StrEnum):
    """State-node categories. Section 3.3 of the Phase 1-2 report."""

    GOAL = "goal"
    DECISION = "decision"
    CONSTRAINT = "constraint"
    OPEN_QUESTION = "open_question"


class StateNodeStatus(StrEnum):
    """Lifecycle status of a state node.

    Status values are type-specific — see ``VALID_STATUSES_BY_TYPE``.
    Terminal statuses (those that block further updates) are listed in
    ``TERMINAL_STATUSES_BY_TYPE``. Default initial status per type is in
    ``DEFAULT_STATUS_BY_TYPE``.

    Section 3.3.1 of the Phase 1-2 report.
    """

    ACTIVE = "active"       # goal, decision, constraint: starting status
    OPEN = "open"           # open_question: starting status
    ACHIEVED = "achieved"   # goal: terminal
    ABANDONED = "abandoned" # goal: terminal
    REVISED = "revised"     # decision, constraint: non-terminal (can repeat)
    REVERTED = "reverted"   # decision: terminal
    LIFTED = "lifted"       # constraint: terminal
    RESOLVED = "resolved"   # open_question: terminal


#: Which statuses each state-node type may legally take. Enforced by
#: ``StateNode`` so a bad W4 response is rejected at parse time.
VALID_STATUSES_BY_TYPE: dict[StateNodeType, frozenset[StateNodeStatus]] = {
    StateNodeType.GOAL: frozenset(
        {StateNodeStatus.ACTIVE, StateNodeStatus.ACHIEVED, StateNodeStatus.ABANDONED}
    ),
    StateNodeType.DECISION: frozenset(
        {StateNodeStatus.ACTIVE, StateNodeStatus.REVISED, StateNodeStatus.REVERTED}
    ),
    StateNodeType.CONSTRAINT: frozenset(
        {StateNodeStatus.ACTIVE, StateNodeStatus.LIFTED, StateNodeStatus.REVISED}
    ),
    StateNodeType.OPEN_QUESTION: frozenset(
        {StateNodeStatus.OPEN, StateNodeStatus.RESOLVED}
    ),
}

#: Terminal statuses block further updates on that node. Section 3.3.1.
TERMINAL_STATUSES_BY_TYPE: dict[StateNodeType, frozenset[StateNodeStatus]] = {
    StateNodeType.GOAL: frozenset(
        {StateNodeStatus.ACHIEVED, StateNodeStatus.ABANDONED}
    ),
    StateNodeType.DECISION: frozenset({StateNodeStatus.REVERTED}),
    StateNodeType.CONSTRAINT: frozenset({StateNodeStatus.LIFTED}),
    StateNodeType.OPEN_QUESTION: frozenset({StateNodeStatus.RESOLVED}),
}

#: Correct starting status for each state-node type. Section 5.7, DEFAULT_STATUS_BY_TYPE.
DEFAULT_STATUS_BY_TYPE: dict[StateNodeType, StateNodeStatus] = {
    StateNodeType.GOAL: StateNodeStatus.ACTIVE,
    StateNodeType.DECISION: StateNodeStatus.ACTIVE,
    StateNodeType.CONSTRAINT: StateNodeStatus.ACTIVE,
    StateNodeType.OPEN_QUESTION: StateNodeStatus.OPEN,
}


class StateRelation(StrEnum):
    """
    How an interaction relates to an existing state node (W4 ``relates``).
    ``RESOLVES`` is the only one that also changes the target's status.
    Section 3.4.2 of the Phase 1-2 report.
    """

    SUPPORTS = "supports"
    CONTRADICTS = "contradicts"
    CONSTRAINED_BY = "constrained_by"
    RESOLVES = "resolves"


#: Default entity-type vocabulary: name -> one-line description, in the shape a
#: W1/combined prompt renders directly into its "allowed types" list. This is
#: a *starting point* used when a conversation has no domain-specific config
#: (``ConversationMeta.entity_type_vocab`` is ``None``), not a closed schema -
#: see the module docstring. Kept as a plain dict (not a ``StrEnum``) because
#: the whole point is that this set is meant to be extended per domain without
#: touching code; ``core/schema/entity.py``'s ``Entity.type`` is a plain
#: ``str``, validated against whichever vocabulary is active for a given
#: conversation (``core/pipeline/steps.py::resolve_entity_vocab``), not against
#: a value here.
DEFAULT_ENTITY_TYPES: dict[str, str] = {
    "person": "A named individual.",
    "organization": "A company, institution, or other named group.",
    "system": "A named software system, platform, or technical component.",
    "location": "A named place.",
    "document": "A named document, report, or written artefact.",
    "tool": "A named tool, library, or protocol/method (e.g. an HTTP verb).",
    "event": "A named occurrence or meeting.",
    "measurement": "A named field, metric, or quantity.",
    "other": "Doesn't fit any other type. Last resort, not a first choice.",
}

#: The fallback type for an entity whose extracted type isn't in the active
#: vocabulary and wasn't a ``propose:`` suggestion either (a plain hallucinated
#: label). Never silently dropped - always ``DEFAULT_ENTITY_TYPE_FALLBACK``.
DEFAULT_ENTITY_TYPE_FALLBACK = "other"


class Granularity(StrEnum):
    """
    How much of an interaction node to inject into context.
    Section 3.6 — three compression tiers.
    """

    FULL = "full"          # question + answer verbatim
    SUMMARY = "summary"    # one-sentence paraphrase (W5)
    REFERENCE = "reference"  # live-rendered pointer or W5 fallback phrase
