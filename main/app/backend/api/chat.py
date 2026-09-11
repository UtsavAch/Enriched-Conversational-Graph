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

import asyncio
import json
import logging
import os
import threading
from collections import defaultdict
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
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
from core.pipeline.orchestrator import OnEvent

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/chat", tags=["chat"])

CHAT_ENABLED = os.environ.get("GM_ENABLE_CHAT") == "1"

#: See the module docstring. Per-conversation, in-process only.
_locks: dict[str, threading.Lock] = defaultdict(threading.Lock)


class ChatRequest(BaseModel):
    conversation_id: str
    question: str
    #: Supply to ingest a pre-existing turn instead of generating an answer.
    answer: str | None = None


def _run_turn(
    repo: JsonConversationRepository,
    client: Any,
    embedder: Any,
    assembler: Any,
    settings: Any,
    request: ChatRequest,
    on_event: OnEvent | None = None,
) -> dict:
    """Shared by both routes below: load-or-create, process, save, view."""
    with _locks[request.conversation_id]:
        if repo.exists(request.conversation_id):
            graph = repo.load(request.conversation_id)
        else:
            graph = repo.create(request.conversation_id, source="live")

        pipeline = TurnPipeline(client, embedder, settings, assembler=assembler)
        result = pipeline.process_turn(
            graph, request.question, answer=request.answer, on_event=on_event
        )
        repo.save(graph)

    return {
        "answer": result.node.answer,
        "turn": result.summary(),
        "graph": build_graph_view(graph),
    }


def _require_chat_enabled() -> None:
    if not CHAT_ENABLED:
        raise HTTPException(
            403,
            "live chat is disabled. Set GM_ENABLE_CHAT=1 to enable, and read "
            "app/backend/api/chat.py first - there is a concurrency caveat.",
        )


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
    _require_chat_enabled()
    return _run_turn(repo, client, embedder, assembler, settings, request)


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


@router.post("/turn/stream")
async def post_turn_stream(
    request: ChatRequest,
    repo: JsonConversationRepository = Depends(get_conversation_repository),
    client=Depends(get_llm_client),
    embedder=Depends(get_embedder),
    assembler=Depends(get_assembler),
    settings=Depends(get_settings),
) -> StreamingResponse:
    """Same turn as ``POST /turn``, streamed as Server-Sent Events.

    Event sequence: a few coarse phase events while context is assembled
    ("thinking", "retrieving_context", "retrieving_documents" - each only
    fired if that work is actually happening), ``answer_delta`` events
    carrying live text as the model generates its reply, one more phase event
    ("updating_memory") once extraction starts, then ``done`` with the same
    payload ``/turn`` returns synchronously - or ``error``.

    Never streams anything from the extraction calls (W1-W5 stay opaque to
    this), and never anything but final-answer text from the model itself -
    see ``StreamingCompletion`` in ``core/llm/client.py``, which is what makes
    that true structurally rather than by convention.

    Runs the pipeline (synchronous, thread-based internally) in a worker
    thread and bridges its ``on_event`` callback into this coroutine's queue.
    Holds the same per-conversation lock, for the same span, as the
    synchronous route above - this changes what gets reported while a turn
    runs, not the concurrency-safety story around it.
    """
    _require_chat_enabled()

    loop = asyncio.get_running_loop()
    queue: asyncio.Queue[tuple[str, dict] | None] = asyncio.Queue()

    def on_event(phase: str, data: dict) -> None:
        loop.call_soon_threadsafe(queue.put_nowait, (phase, data))

    def run() -> dict:
        return _run_turn(repo, client, embedder, assembler, settings, request, on_event)

    async def event_stream():
        task = asyncio.create_task(asyncio.to_thread(run))
        task.add_done_callback(lambda _fut: queue.put_nowait(None))

        while True:
            item = await queue.get()
            if item is None:
                break
            phase, data = item
            yield _sse(phase, data)

        try:
            result = task.result()
        except Exception as exc:
            logger.exception(
                "streamed turn failed: conversation_id=%r", request.conversation_id
            )
            yield _sse("error", {"detail": str(exc)})
            return
        yield _sse("done", result)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
