"""Persistence layer. JSON today; the interfaces are what matter."""

from core.persistence.base import ConversationRepository, DocumentRepository
from core.persistence.json_repository import (
    JsonConversationRepository,
    JsonDocumentRepository,
    attach_document_to_conversation,
)

__all__ = [
    "ConversationRepository",
    "DocumentRepository",
    "JsonConversationRepository",
    "JsonDocumentRepository",
    "attach_document_to_conversation",
]
