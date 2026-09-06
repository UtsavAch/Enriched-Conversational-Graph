"""Retrieval: candidate selection for extraction, context assembly for answering."""

from core.retrieval.candidate_selection import (
    Candidate,
    render_candidates,
    select_edge_candidates,
)
from core.retrieval.context_assembly import (
    AssembledContext,
    ContextAssembler,
    ContextItem,
)

__all__ = [
    "AssembledContext",
    "Candidate",
    "ContextAssembler",
    "ContextItem",
    "render_candidates",
    "select_edge_candidates",
]
