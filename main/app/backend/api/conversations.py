"""Conversation listing, retrieval, and document scoping."""

from __future__ import annotations

import re

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.backend.dependencies import get_conversation_repository, get_document_repository
from core.persistence import (
    JsonConversationRepository,
    JsonDocumentRepository,
    get_conversation_document_ids,
    reference_document_in_conversation,
    unreference_document_in_conversation,
)

router = APIRouter(prefix="/api/conversations", tags=["conversations"])


class CreateConversationRequest(BaseModel):
    title: str
    #: Explicit override, for programmatic callers (CLI-adjacent tooling). The
    #: app's own "New conversation" dialog never sends this - it only asks for
    #: a topic and lets the id be generated, see ``_unique_conversation_id``.
    conversation_id: str | None = None


def _slugify(text: str) -> str:
    """Turn free text into a safe, readable id fragment.

    Only ``[a-z0-9_]`` survive, so the result can never collide with the
    "unsafe id" check in ``JsonConversationRepository`` (no ``/``, no leading
    ``.``). Falls back to a generic word if the title slugifies to nothing
    (e.g. it was all punctuation/emoji).
    """
    slug = re.sub(r"[^a-z0-9]+", "_", text.strip().lower()).strip("_")
    return slug[:40] or "conversation"


def _unique_conversation_id(repo: JsonConversationRepository, title: str) -> str:
    """Slugify ``title`` into an id, appending ``_2``, ``_3``, ... on collision."""
    base = _slugify(title)
    candidate = base
    n = 2
    while repo.exists(candidate):
        candidate = f"{base}_{n}"
        n += 1
    return candidate


@router.get("")
def list_conversations(
    repo: JsonConversationRepository = Depends(get_conversation_repository),
) -> list[dict]:
    """Summary of every stored conversation, for the sidebar picker."""
    out = []
    for cid in repo.list_conversations():
        graph = repo.load(cid)
        out.append(
            {
                "conversation_id": cid,
                "title": graph.meta.title,
                "source": graph.meta.source,
                "n_turns": len(graph.interactions),
                "n_entities": len(graph.entities),
                "n_state_nodes": len(graph.state_nodes),
                "updated_at": graph.meta.updated_at,
            }
        )
    return sorted(out, key=lambda c: c["updated_at"], reverse=True)


@router.post("")
def create_conversation(
    payload: CreateConversationRequest,
    repo: JsonConversationRepository = Depends(get_conversation_repository),
) -> dict:
    """Create an empty conversation from a topic - no first turn.

    Deliberately decoupled from the chat endpoint (which used to be the only
    way a conversation came into existence, on its first turn). Splitting
    creation out means a conversation can have documents selected for it (see
    the /documents routes below) *before* the first message is ever sent, so
    that first turn is scoped correctly instead of silently falling back to
    the entire global document corpus.

    The id is generated from ``title`` (see ``_unique_conversation_id``)
    unless the caller explicitly supplies one - the app's own dialog only ever
    sends a title, since asking a person to also invent a unique id is the
    kind of busywork this endpoint exists to remove.
    """
    try:
        if payload.conversation_id:
            # An explicit id is a real conflict to report, not something to
            # silently work around - only auto-generated ids get de-duplicated.
            if repo.exists(payload.conversation_id):
                raise HTTPException(
                    409, f"conversation '{payload.conversation_id}' already exists"
                )
            conversation_id = payload.conversation_id
        else:
            conversation_id = _unique_conversation_id(repo, payload.title)
        graph = repo.create(conversation_id, title=payload.title, source="live")
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return {"conversation_id": graph.meta.conversation_id, "title": graph.meta.title}


@router.get("/{conversation_id}/turns")
def get_turns(
    conversation_id: str,
    repo: JsonConversationRepository = Depends(get_conversation_repository),
) -> list[dict]:
    """The chat transcript, in turn order. Feeds the left-hand chat panel."""
    try:
        graph = repo.load(conversation_id)
    except KeyError:
        raise HTTPException(404, f"no conversation '{conversation_id}'") from None
    return [
        {
            "id": n.id,
            "turn_index": n.turn_index,
            "timestamp": n.timestamp,
            "question": n.question,
            "answer": n.answer,
            "speech_act": n.speech_act.value,
            "epistemic_status": n.epistemic_status.value,
        }
        for n in graph.ordered_interactions()
    ]


@router.delete("/{conversation_id}")
def delete_conversation(
    conversation_id: str,
    repo: JsonConversationRepository = Depends(get_conversation_repository),
) -> dict:
    repo.delete(conversation_id)
    return {"deleted": conversation_id}


@router.get("/{conversation_id}/documents")
def get_conversation_documents(
    conversation_id: str,
    doc_repo: JsonDocumentRepository = Depends(get_document_repository),
) -> list[dict]:
    """Documents this conversation's retrieval is scoped to - uploaded through
    it or explicitly selected from the global corpus. Empty means this
    conversation has no document grounding at all - there is no fallback to
    the global corpus, see ``ContextAssembler._add_document_context``.
    """
    out = []
    for source_id in get_conversation_document_ids(conversation_id):
        try:
            out.append(doc_repo.get_source(source_id).model_dump(mode="json"))
        except KeyError:
            continue  # referenced but since deleted from the global store
    return out


@router.post("/{conversation_id}/documents/{source_id}")
def select_conversation_document(
    conversation_id: str,
    source_id: str,
    doc_repo: JsonDocumentRepository = Depends(get_document_repository),
) -> dict:
    """Scope this conversation's retrieval to include an already-ingested
    document, without re-uploading it. See ``reference_document_in_conversation``.
    """
    try:
        source = doc_repo.get_source(source_id)
    except KeyError:
        raise HTTPException(404, f"no document '{source_id}'") from None
    reference_document_in_conversation(conversation_id, source)
    return {"selected": source_id}


@router.delete("/{conversation_id}/documents/{source_id}")
def deselect_conversation_document(conversation_id: str, source_id: str) -> dict:
    """Remove a document from this conversation's retrieval scope. Harmless if
    it was never referenced."""
    unreference_document_in_conversation(conversation_id, source_id)
    return {"deselected": source_id}


# --- entity type suggestions ------------------------------------------------
# See evaluation_report.md section 8: W1's "propose:<label>" escape hatch
# records a PendingEntityTypeSuggestion instead of applying a new type
# unilaterally. These three endpoints are the human-in-the-loop step that
# actually grows a conversation's entity_type_vocab.


def _load_or_404(
    conversation_id: str, repo: JsonConversationRepository
):
    try:
        return repo.load(conversation_id)
    except KeyError:
        raise HTTPException(404, f"no conversation '{conversation_id}'") from None


@router.get("/{conversation_id}/entity-type-suggestions")
def get_entity_type_suggestions(
    conversation_id: str,
    repo: JsonConversationRepository = Depends(get_conversation_repository),
) -> list[dict]:
    """Pending ``propose:`` suggestions, for a non-blocking UI badge to poll."""
    graph = _load_or_404(conversation_id, repo)
    return [s.model_dump(mode="json") for s in graph.meta.pending_entity_type_suggestions]


@router.post("/{conversation_id}/entity-type-suggestions/{label}/confirm")
def confirm_entity_type_suggestion(
    conversation_id: str,
    label: str,
    repo: JsonConversationRepository = Depends(get_conversation_repository),
) -> dict:
    """Adopt a proposed type for this conversation and backfill matching entities.

    Backfill: entities already stored as ``"other"`` (the fallback
    ``_parse_entities`` gives a ``propose:`` entity while it's unconfirmed)
    whose name matches one of the suggestion's recorded examples are retyped -
    so confirming benefits entities mentioned before the confirmation click,
    not just ones extracted after it. Per-conversation only: no cross-conversation
    preset is written (see evaluation_report.md section 8's scope decision).
    """
    graph = _load_or_404(conversation_id, repo)
    pending = graph.meta.pending_entity_type_suggestions
    suggestion = next((s for s in pending if s.label == label), None)
    if suggestion is None:
        raise HTTPException(404, f"no pending suggestion '{label}'")

    vocab = graph.meta.entity_type_vocab or {}
    vocab[label] = suggestion.description or f"Domain-specific type: {label}."
    graph.meta.entity_type_vocab = vocab

    examples = {name.strip().lower() for name in suggestion.example_entity_names}
    backfilled = []
    for entity in graph.entities.values():
        if entity.type == "other" and entity.normalised_name() in examples:
            entity.type = label
            backfilled.append(entity.id)

    graph.meta.pending_entity_type_suggestions = [s for s in pending if s.label != label]
    repo.save(graph)
    return {"confirmed": label, "backfilled_entities": backfilled}


@router.post("/{conversation_id}/entity-type-suggestions/{label}/reject")
def reject_entity_type_suggestion(
    conversation_id: str,
    label: str,
    repo: JsonConversationRepository = Depends(get_conversation_repository),
) -> dict:
    """Drop a suggestion. Matching entities stay ``"other"`` - identical to
    today's behaviour if a suggestion is simply never acted on."""
    graph = _load_or_404(conversation_id, repo)
    before = len(graph.meta.pending_entity_type_suggestions)
    graph.meta.pending_entity_type_suggestions = [
        s for s in graph.meta.pending_entity_type_suggestions if s.label != label
    ]
    if len(graph.meta.pending_entity_type_suggestions) == before:
        raise HTTPException(404, f"no pending suggestion '{label}'")
    repo.save(graph)
    return {"rejected": label}
