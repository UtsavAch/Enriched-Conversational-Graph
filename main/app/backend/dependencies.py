"""Wiring. The only place the app decides which concrete implementations to use.

Everything else in the app depends on interfaces. Swapping the JSON repository
for a database one, or the hashing embedder for a real model, is an edit to this
file and nothing else.

Components are cached at module level because they are stateless and expensive
to construct (an embedding model load is seconds). FastAPI's ``Depends`` gives
each request the same instance.
"""

from __future__ import annotations

import functools
import logging
import os

from core.config import Settings
from core.llm.client import LLMClient, StubLLMClient
from core.llm.embeddings import Embedder, build_embedder
from core.persistence import JsonConversationRepository, JsonDocumentRepository
from core.retrieval.context_assembly import ContextAssembler
from core.retrieval.rag import DocumentIngestor, SimpleRagRetriever

logger = logging.getLogger(__name__)


@functools.lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


@functools.lru_cache(maxsize=1)
def get_embedder() -> Embedder:
    s = get_settings()
    return build_embedder(s.models.embedding_model, s.models.embedding_dim)


@functools.lru_cache(maxsize=1)
def get_llm_client() -> LLMClient:
    """Select the LLM client based on available credentials.

    Priority: OpenAI-compatible endpoint (GM_OPENAI_BASE_URL) > Anthropic API
    key > StubLLMClient fallback. Falling back to the stub rather than failing
    at startup is deliberate: the read-only inspection endpoints do not need a
    model at all, and requiring an API key to inspect an already-built graph
    would be a pointless barrier for a reviewer or supervisor.
    """
    s = get_settings()
    if s.models.openai_base_url:
        from core.llm.client import OpenAICompatClient  # noqa: PLC0415

        logger.info(
            "Using OpenAI-compatible endpoint: %s model=%s",
            s.models.openai_base_url,
            s.models.extraction_model,
        )
        return OpenAICompatClient(
            model=s.models.extraction_model,
            base_url=s.models.openai_base_url,
            api_key=s.models.openai_api_key,
        )
    if os.environ.get("ANTHROPIC_API_KEY"):
        from core.llm.client import AnthropicClient  # noqa: PLC0415

        return AnthropicClient(s.models.extraction_model)
    logger.warning(
        "Neither GM_OPENAI_BASE_URL nor ANTHROPIC_API_KEY is set — using "
        "StubLLMClient. Read-only endpoints work fully; live chat will return "
        "empty answers."
    )
    return StubLLMClient()


@functools.lru_cache(maxsize=1)
def get_conversation_repository() -> JsonConversationRepository:
    return JsonConversationRepository()


@functools.lru_cache(maxsize=1)
def get_document_repository() -> JsonDocumentRepository:
    return JsonDocumentRepository()


@functools.lru_cache(maxsize=1)
def get_rag_retriever() -> SimpleRagRetriever:
    return SimpleRagRetriever(
        get_document_repository(), get_embedder(), get_settings().rag
    )


@functools.lru_cache(maxsize=1)
def get_ingestor() -> DocumentIngestor:
    return DocumentIngestor(get_document_repository(), get_embedder(), get_settings().rag)


@functools.lru_cache(maxsize=1)
def get_assembler() -> ContextAssembler:
    return ContextAssembler(get_embedder(), get_rag_retriever())
