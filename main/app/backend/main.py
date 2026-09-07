"""FastAPI application for the memory-graph inspector (workplan task 5.2).

Run it::

    cd main
    uvicorn app.backend.main:app --reload

then open http://127.0.0.1:8000/

The app is a *thin* layer. It contains no extraction logic, no retrieval logic,
no schema knowledge beyond the view-model adapter. Everything it does, it does by
calling ``core``. That is what keeps the system the thesis evaluates and the
system a supervisor is shown from drifting apart.
"""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.backend.api import chat, conversations, documents, graph
from core import __version__

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"

app = FastAPI(
    title="Graph-Augmented Conversational Memory",
    version=__version__,
    description=(
        "Inspection and visualisation surface for the enriched conversational "
        "memory graph. Read-only by default; live chat is opt-in."
    ),
)

# Permissive CORS because the frontend is often opened as a file:// page during
# development. Tighten this before any deployment beyond localhost.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(conversations.router)
app.include_router(graph.router)
app.include_router(documents.router)
app.include_router(chat.router)


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "version": __version__, "chat_enabled": chat.CHAT_ENABLED}


if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")

    @app.get("/")
    def index() -> FileResponse:
        return FileResponse(str(FRONTEND_DIR / "index.html"))
