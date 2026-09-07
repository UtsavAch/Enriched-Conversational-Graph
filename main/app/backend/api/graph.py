"""Graph view endpoints - the core of task 5.2.

These are read-only. They serve an already-built graph for inspection; they do
not build one. That separation is what lets the visualisation be opened by
anyone, with no API key and no risk of mutating research data.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.backend.dependencies import get_conversation_repository
from app.backend.view_model import build_graph_view, build_node_detail
from core.graph import GraphStore, connected_component
from core.persistence import JsonConversationRepository

router = APIRouter(prefix="/api/graph", tags=["graph"])


@router.get("/{conversation_id}")
def get_graph(
    conversation_id: str,
    repo: JsonConversationRepository = Depends(get_conversation_repository),
) -> dict:
    """The full flattened graph. This is what the D3 view loads on startup."""
    try:
        graph = repo.load(conversation_id)
    except KeyError:
        raise HTTPException(404, f"no conversation '{conversation_id}'") from None
    return build_graph_view(graph)


@router.get("/{conversation_id}/node/{node_id}")
def get_node(
    conversation_id: str,
    node_id: str,
    repo: JsonConversationRepository = Depends(get_conversation_repository),
) -> dict:
    """Detail panel payload for one node of any kind."""
    try:
        graph = repo.load(conversation_id)
        return build_node_detail(graph, node_id)
    except KeyError:
        raise HTTPException(404, f"no node '{node_id}' in '{conversation_id}'") from None


@router.get("/{conversation_id}/stats")
def get_stats(
    conversation_id: str,
    repo: JsonConversationRepository = Depends(get_conversation_repository),
) -> dict:
    """Edge/node counts plus integrity warnings.

    Worth watching during Phase 3 validation. Two things to look for:
    a relation type with a near-zero count (the thinness problem the thesis
    observed), and a graph that splits into many components (the classifier
    emitting no_relation too freely).
    """
    try:
        graph = repo.load(conversation_id)
    except KeyError:
        raise HTTPException(404, f"no conversation '{conversation_id}'") from None

    store = GraphStore(graph)
    ordered = graph.ordered_interactions()
    components: list[set[str]] = []
    seen: set[str] = set()
    for node in ordered:
        if node.id in seen:
            continue
        comp = connected_component(store, node.id)
        components.append(comp)
        seen |= comp

    return {
        "counts": store.stats(),
        "n_components": len(components),
        "largest_component": max((len(c) for c in components), default=0),
        "isolated_nodes": [n.id for n in ordered if store.degree(n.id) == 0],
        "dangling_references": graph.dangling_references(),
    }
