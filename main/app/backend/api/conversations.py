"""Conversation listing and retrieval. Read-only."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.backend.dependencies import get_conversation_repository
from core.persistence import JsonConversationRepository

router = APIRouter(prefix="/api/conversations", tags=["conversations"])


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
            "date": n.date,
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
