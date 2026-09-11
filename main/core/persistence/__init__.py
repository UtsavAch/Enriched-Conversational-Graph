"""Persistence layer. JSON today; the interfaces are what matter."""

from core.persistence.base import ConversationRepository, DocumentRepository
from core.persistence.json_repository import (
    JsonConversationRepository,
    JsonDocumentRepository,
    attach_document_to_conversation,
    document_usage_map,
    find_conversations_referencing_document,
    get_conversation_document_ids,
    reference_document_in_conversation,
    unreference_document_in_conversation,
)

__all__ = [
    "ConversationRepository",
    "DocumentRepository",
    "JsonConversationRepository",
    "JsonDocumentRepository",
    "attach_document_to_conversation",
    "document_usage_map",
    "find_conversations_referencing_document",
    "get_conversation_document_ids",
    "reference_document_in_conversation",
    "unreference_document_in_conversation",
]
