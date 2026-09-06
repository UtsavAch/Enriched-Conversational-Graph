"""State nodes: goals, decisions, constraints and open questions.

Where interaction nodes record *what was said*, state nodes record *what is
currently true of the project*. This is the layer that lets the agent answer
"are we still keeping all five edge types?" without re-reading ten turns.

A state node is created once and then updated in place. It is the only part of
the graph that is genuinely mutable, which is why its status transitions are
validated rather than trusted.
"""

from __future__ import annotations

from pydantic import BaseModel, Field, model_validator

from core.schema.enums import (
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
    status: StateNodeStatus = StateNodeStatus.ACTIVE

    #: Audit trail. Split into two lists mirroring W4's own output shape, so a
    #: W4 response maps onto storage without a lossy transformation.
    updates: list[StateNodeUpdate] = Field(default_factory=list)
    relations: list[StateNodeRelationRef] = Field(default_factory=list)

    @model_validator(mode="after")
    def _status_valid_for_type(self) -> "StateNode":
        allowed = VALID_STATUSES_BY_TYPE[self.type]
        if self.status not in allowed:
            raise ValueError(
                f"status '{self.status}' is not valid for state node type "
                f"'{self.type}'. Allowed: {sorted(s.value for s in allowed)}"
            )
        return self

    @property
    def last_updated_turn(self) -> str:
        """Most recent turn that touched this node, falling back to creation."""
        turns = [u.turn for u in self.updates] + [r.turn for r in self.relations]
        return turns[-1] if turns else self.creation_turn

    @property
    def is_open(self) -> bool:
        """Whether this node should be offered to W4 as a merge candidate.

        Only open state nodes are worth showing to the merge call: a resolved
        question or an abandoned goal cannot sensibly be updated again, and
        including them just burns prompt tokens and invites bad merges.
        """
        return self.status in (StateNodeStatus.ACTIVE,)

    def apply_update(self, turn: str, new_status: StateNodeStatus) -> None:
        """Record a status change, validating it is legal for this node's type."""
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
        alongside it), so this method deliberately does *not* mutate status -
        keeping one and only one code path that can change it.
        """
        self.relations.append(StateNodeRelationRef(turn=turn, relation=relation))
