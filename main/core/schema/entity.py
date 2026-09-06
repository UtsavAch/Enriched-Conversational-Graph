"""Entities: the people, systems, documents and so on a conversation refers to.

Entities are a *second layer* of nodes. They are not interactions and carry no
discourse relations. Their job is to give retrieval a non-semantic handle: two
turns that share no vocabulary can still be connected because both mention the
same entity.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from core.schema.enums import EntityType


class Entity(BaseModel):
    """A named entity, deduplicated across the whole conversation.
    An entity is created once and then *referenced* on each later mention by ``mentioned_in``. 
    It is never regenerated.
    """

    id: str = Field(..., description="Stable id, convention 'E_<n>'.")
    conversation_id: str
    type: EntityType
    name: str = Field(..., description="Surface form as first mentioned.")
    mentioned_in: list[str] = Field(
        default_factory=list, description="Interaction node ids mentioning this entity."
    )
    aliases: list[str] = Field(
        default_factory=list,
        description="Other surface forms merged into this entity. Empty until an "
        "entity-merge step exists; kept in the schema so adding one later is not "
        "a migration.",
    )

    def normalised_name(self) -> str:
        """Cheap normalisation used for exact-match deduplication.

        Intentionally naive: lowercase and strip. Anything smarter (embedding
        similarity, an LLM merge call) is a design decision that should be made
        with validation data in front of you, not guessed here.
        """
        return self.name.strip().lower()
