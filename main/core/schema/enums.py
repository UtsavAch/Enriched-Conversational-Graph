"""Every enum here corresponds directly to a field.. Keeping them as enums rather than
free strings means an LLM extraction call that hallucinates a label fails loudly
at parse time instead of silently polluting the graph.

If you add a value here you are changing the schema. Bump ``SCHEMA_VERSION`` in
``core/schema/__init__.py`` when you do.
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
    Topic-structure relations.
    """

    SUBCASE = "subcase"
    SUPERCASE = "supercase"
    SAME_LEVEL = "same_level"


class PragmaticRelation(StrEnum):
    """
    Pragmatic relations.
    """

    REVISES = "revises"
    CONTRADICTS = "contradicts"
    RESOLVES = "resolves"
    DEPENDS_ON = "depends_on"
    REFERENCES = "references"


class StateNodeType(StrEnum):
    """State-nodes"""

    GOAL = "goal"
    DECISION = "decision"
    CONSTRAINT = "constraint"
    OPEN_QUESTION = "open_question"


class StateNodeStatus(StrEnum):
    """Lifecycle status of a state node.

    Not every status is valid for every type; see ``VALID_STATUSES_BY_TYPE``.
    """

    ACTIVE = "active"
    ACHIEVED = "achieved"
    ABANDONED = "abandoned"
    REVISED = "revised"
    SUPERSEDED = "superseded"
    SATISFIED = "satisfied"
    VIOLATED = "violated"
    RESOLVED = "resolved"


#: Which statuses each state-node type may legally take.
#: Enforced in ``StateNode`` validation so a bad W4 output is rejected at parse
#: time rather than producing a state node in an impossible state.
VALID_STATUSES_BY_TYPE: dict[StateNodeType, frozenset[StateNodeStatus]] = {
    StateNodeType.GOAL: frozenset(
        {
            StateNodeStatus.ACTIVE,
            StateNodeStatus.ACHIEVED,
            StateNodeStatus.ABANDONED,
            StateNodeStatus.REVISED,
        }
    ),
    StateNodeType.DECISION: frozenset(
        {
            StateNodeStatus.ACTIVE,
            StateNodeStatus.REVISED,
            StateNodeStatus.SUPERSEDED,
        }
    ),
    StateNodeType.CONSTRAINT: frozenset(
        {
            StateNodeStatus.ACTIVE,
            StateNodeStatus.SATISFIED,
            StateNodeStatus.VIOLATED,
            StateNodeStatus.REVISED,
        }
    ),
    StateNodeType.OPEN_QUESTION: frozenset(
        {
            StateNodeStatus.ACTIVE,
            StateNodeStatus.RESOLVED,
            StateNodeStatus.ABANDONED,
        }
    ),
}


class StateRelation(StrEnum):
    """
    How an interaction relates to an existing state node (W4 ``relates``).
    ``RESOLVES`` is the only one that may change the target's status.
    """

    SUPPORTS = "supports"
    CONTRADICTS = "contradicts"
    CONSTRAINED_BY = "constrained_by"
    RESOLVES = "resolves"


class EntityType(StrEnum):
    """
    Entity categories.
    This list may need to be revised for deployments in other domains.
    """

    PERSON = "person"
    ORGANIZATION = "organization"
    SYSTEM = "system"
    LOCATION = "location"
    DOCUMENT = "document"
    TOOL = "tool"
    EVENT = "event"
    MEASUREMENT = "measurement"
    OTHER = "other"


class Granularity(StrEnum):
    """
    How much of an interaction node to inject into context.
    """

    FULL = "full"          # question + answer
    SUMMARY = "summary"    # one-sentence summary
    REFERENCE = "reference"  # a few words
