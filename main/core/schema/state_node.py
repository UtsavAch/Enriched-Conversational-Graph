"""State nodes: goals, decisions, constraints and open questions.

Where interaction nodes record *what was said*, state nodes record *what is
currently true of the project*. This is the layer that lets the agent answer
"are we still keeping all five edge types?" without re-reading ten turns.

A state node is created once and then updated in place. It is the only part of
the graph that is genuinely mutable, which is why its status transitions are
validated rather than trusted.

Section 3.3 of the Phase 1-2 report.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field, model_validator

from core.schema.enums import (
    DEFAULT_STATUS_BY_TYPE,
    TERMINAL_STATUSES_BY_TYPE,
    VALID_STATUSES_BY_TYPE,
    StateNodeStatus,
    StateNodeType,
    StateRelation,
)


class StateNodeUpdate(BaseModel):
    """One recorded change to a state node's status."""

    turn: str = Field(..., description="Interaction node id that caused the change.")
    new_status: StateNodeStatus

    model_config = {"frozen": True}


class StateNodeRelationRef(BaseModel):
    """A recorded relation from an interaction to this state node."""

    turn: str
    relation: StateRelation

    model_config = {"frozen": True}


class StateNode(BaseModel):
    """A goal, decision, constraint, or open question tracked across the dialogue."""

    id: str = Field(..., description="Stable id, convention 'SN_<n>'.")
    conversation_id: str
    type: StateNodeType
    label: str = Field(..., description="Short summary, produced by W4.")
    embedding: list[float] | None = Field(
        None, description="Embedding of ``label``, for state-node retrieval."
    )
    creation_turn: str = Field(..., description="Interaction id that created this.")
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="ISO 8601 timestamp of the turn that created this state node.",
    )

    # Status defaults are type-specific — see DEFAULT_STATUS_BY_TYPE.
    # Do not hardcode ACTIVE here in calls; use StateNode.initial_status(type).
    status: StateNodeStatus = StateNodeStatus.ACTIVE

    #: Audit trail. Split into two lists mirroring W4's own output shape.
    updates: list[StateNodeUpdate] = Field(default_factory=list)
    relations: list[StateNodeRelationRef] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def _apply_type_default_status(cls, data: Any) -> Any:
        """Set the correct default status for the node's type when not supplied.

        open_question starts as OPEN, not ACTIVE. goal/decision/constraint
        start as ACTIVE. Callers should use ``StateNode.initial_status(type)``
        or pass status explicitly; this validator is the safety net.
        """
        if isinstance(data, dict) and data.get("status") is None:
            stype = data.get("type")
            if stype is not None:
                try:
                    stype_enum = StateNodeType(stype)
                    data["status"] = DEFAULT_STATUS_BY_TYPE[stype_enum].value
                except (ValueError, KeyError):
                    pass
        return data

    @model_validator(mode="after")
    def _status_valid_for_type(self) -> "StateNode":
        allowed = VALID_STATUSES_BY_TYPE[self.type]
        if self.status not in allowed:
            raise ValueError(
                f"status '{self.status}' is not valid for state node type "
                f"'{self.type}'. Allowed: {sorted(s.value for s in allowed)}"
            )
        return self

    @staticmethod
    def initial_status(node_type: StateNodeType) -> StateNodeStatus:
        """Return the correct starting status for a newly created state node."""
        return DEFAULT_STATUS_BY_TYPE[node_type]

    @property
    def last_updated_turn(self) -> str:
        """Most recent turn that touched this node, falling back to creation."""
        turns = [u.turn for u in self.updates] + [r.turn for r in self.relations]
        return turns[-1] if turns else self.creation_turn

    @property
    def is_open(self) -> bool:
        """Whether this node should be offered to W4 as a merge candidate.

        Per section 5.5: filter = status IN {"active", "open"}.
        Only ACTIVE (goal/decision/constraint) and OPEN (open_question) nodes
        are shown to W4. Terminal nodes and REVISED nodes are excluded.
        REVISED is excluded because a revised decision/constraint is still
        live but showing it to W4 would invite redundant further updates.
        """
        return self.status in (StateNodeStatus.ACTIVE, StateNodeStatus.OPEN)

    @property
    def is_terminal(self) -> bool:
        """Whether this node's status is terminal and cannot be updated further."""
        return self.status in TERMINAL_STATUSES_BY_TYPE[self.type]

    def apply_update(self, turn: str, new_status: StateNodeStatus) -> None:
        """Record a status change, validating it is legal for this node's type.

        Rejects updates to nodes already in a terminal status. Section 3.3.1:
        "apply_w4 checks sn.status IN TERMINAL_STATUSES[sn.type] before
        allowing any update, and rejects the update if already terminal."
        """
        if self.is_terminal:
            raise ValueError(
                f"state node '{self.id}' is already in terminal status "
                f"'{self.status}' — no further updates are allowed"
            )
        allowed = VALID_STATUSES_BY_TYPE[self.type]
        if new_status not in allowed:
            raise ValueError(
                f"cannot set status '{new_status}' on a '{self.type}' state node"
            )
        self.status = new_status
        self.updates.append(StateNodeUpdate(turn=turn, new_status=new_status))

    def apply_relation(self, turn: str, relation: StateRelation) -> None:
        """Record a relation from an interaction to this node.

        Most relations do not change status. ``resolves`` is the one exception
        and is handled by the caller (W4 emits an explicit ``updates`` entry
        alongside it), so this method deliberately does *not* mutate status —
        keeping one and only one code path that can change it.
        """
        self.relations.append(StateNodeRelationRef(turn=turn, relation=relation))
