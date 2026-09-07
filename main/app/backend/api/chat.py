"""Live chat: send a turn, get an answer, watch the graph grow.

DISABLED BY DEFAULT. Set ``GM_ENABLE_CHAT=1`` to turn it on.

Why gated rather than simply present:

1. The existing prototype's composer is deliberately inert - task 5.2 as written
   is "extend the prototype to visualise the new node types", a *visualisation*
   deliverable. Live chat is a different, larger feature.
2. Live chat quietly depends on an unresolved design item. The pipeline assumes
   the next turn cannot begin until the current turn's graph write finishes.
   That holds trivially for single-threaded batch ingestion. It does *not* hold
   for a web server with concurrent requests, and nothing in the code enforces
   it. Two overlapping turns on the same conversation will race on id allocation
   and can lose an edge.

The naive mitigation below - one lock per conversation - makes single-process
use safe. It does not survive multiple workers. Fix that properly (or run one
worker) before letting anyone but you use this.
"""

from __future__ import annotations

import os
import threading
from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.backend.dependencies import (
    get_assembler,
    get_conversation_repository,
    get_embedder,
    get_llm_client,
    get_settings,
)
from app.backend.view_model import build_graph_view
from core.persistence import JsonConversationRepository
from core.pipeline import TurnPipeline

router = APIRouter(prefix="/api/chat", tags=["chat"])

CHAT_ENABLED = os.environ.get("GM_ENABLE_CHAT") == "1"

#: See the module docstring. Per-conversation, in-process only.
_locks: dict[str, threading.Lock] = defaultdict(threading.Lock)


class ChatRequest(BaseModel):
    conversation_id: str
    question: str
    #: Supply to ingest a pre-existing turn instead of generating an answer.
    answer: str | None = None


@router.post("/turn")
def post_turn(
    request: ChatRequest,
    repo: JsonConversationRepository = Depends(get_conversation_repository),
    client=Depends(get_llm_client),
    embedder=Depends(get_embedder),
    assembler=Depends(get_assembler),
    settings=Depends(get_settings),
) -> dict:
    """Process one turn and return the answer plus the updated graph view."""
    if not CHAT_ENABLED:
        raise HTTPException(
            403,
            "live chat is disabled. Set GM_ENABLE_CHAT=1 to enable, and read "
            "app/backend/api/chat.py first - there is a concurrency caveat.",
        )

    with _locks[request.conversation_id]:
        if repo.exists(request.conversation_id):
            graph = repo.load(request.conversation_id)
        else:
            graph = repo.create(request.conversation_id, source="live")

        pipeline = TurnPipeline(client, embedder, settings, assembler=assembler)
        result = pipeline.process_turn(graph, request.question, answer=request.answer)
        repo.save(graph)

    return {
        "answer": result.node.answer,
        "turn": result.summary(),
        "graph": build_graph_view(graph),
    }
