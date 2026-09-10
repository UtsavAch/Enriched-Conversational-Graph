"""Adapter: canonical storage schema -> the flat view model the frontend draws.

WHY THIS EXISTS AS A SEPARATE LAYER.

The storage schema is normalised: each interaction owns its outgoing edges, and
state-node links are split into creates/updates/relates. That is right for
storage - it keeps one node in one JSON object with no separate edge table to
keep in sync.

The D3 force layout wants the opposite: a flat node list and a flat edge list,
each edge tagged with a filterable group. Doing that flattening in the browser
would put schema knowledge in JavaScript, where it would silently drift from the
Python definition every time the schema changes.

So the flattening happens here, once, in Python, next to the schema it depends
on. The frontend stays a renderer.

Output shape matches the existing prototype exactly::

    {
      "interaction_nodes": [ {id, timestamp, question, answer, summary, ...}, ... ],
      "entities":          [ {id, type, name, mentioned_in, timestamp}, ... ],
      "state_nodes":       [ {id, type, label, status, creation_turn, timestamp}, ... ],
      "edges":             [ {source, target, label, group}, ... ]
    }
"""

from __future__ import annotations

from typing import Any

from core.graph.graph_store import GraphStore
from core.schema.conversation import ConversationGraph


def build_graph_view(graph: ConversationGraph) -> dict[str, Any]:
    """Flatten a conversation into the frontend's node/edge view model."""
    store = GraphStore(graph)

    interaction_nodes = [
        {
            "id": n.id,
            "timestamp": n.timestamp,
            "turn_index": n.turn_index,
            "question": n.question,
            "answer": n.answer,
            "summary": n.summary or "",
            "reference": n.reference or "",
            "speech_act": n.speech_act.value,
            "epistemic_status": n.epistemic_status.value,
            "recurrence_count": n.recurrence_count,
            "retrieval_count": n.retrieval_count,
            "named_entities": n.named_entities,
            "citations": n.citations,
            "grounded_by": n.grounded_by,
            # The visualisation renders the audit trail as a timeline; sending it
            # flattened saves the frontend from knowing the event schema.
            "epistemic_history": [
                [e.caused_by, e.trigger, e.status.value] for e in n.epistemic_history
            ],
        }
        for n in graph.ordered_interactions()
    ]

    entities = [
        {
            "id": e.id,
            "type": e.type.value,
            "name": e.name,
            "mentioned_in": e.mentioned_in,
            "timestamp": e.timestamp,
        }
        for e in graph.entities.values()
    ]

    state_nodes = [
        {
            "id": sn.id,
            "type": sn.type.value,
            "label": sn.label,
            "status": sn.status.value,
            "creation_turn": sn.creation_turn,
            "last_updated_turn": sn.last_updated_turn,
            "timestamp": sn.timestamp,
        }
        for sn in graph.state_nodes.values()
    ]

    edges = [
        {"source": e.source, "target": e.target, "label": e.relation, "group": e.group}
        for e in store.edges
    ]

    return {
        "conversation_id": graph.meta.conversation_id,
        "title": graph.meta.title,
        "schema_version": graph.meta.schema_version,
        "interaction_nodes": interaction_nodes,
        "entities": entities,
        "state_nodes": state_nodes,
        "edges": edges,
        "stats": store.stats(),
    }


def build_node_detail(graph: ConversationGraph, node_id: str) -> dict[str, Any]:
    """Everything the detail panel shows for one node, whatever kind it is.

    Includes the node's own fields plus every edge touching it, in either
    direction, with the neighbour's display name resolved. Resolving names here
    rather than in the browser means the panel does not need the full node list
    in memory to render one node - which matters once conversations get long.
    """
    store = GraphStore(graph)

    if node_id in graph.interactions:
        node = graph.interactions[node_id]
        kind = "interaction"
        payload = node.model_dump(mode="json", exclude={"embedding"})
    elif node_id in graph.entities:
        node = graph.entities[node_id]
        kind = "entity"
        payload = node.model_dump(mode="json")
    elif node_id in graph.state_nodes:
        node = graph.state_nodes[node_id]
        kind = "state"
        payload = node.model_dump(mode="json", exclude={"embedding"})
    else:
        raise KeyError(node_id)

    def display_name(nid: str) -> str:
        if nid in graph.interactions:
            n = graph.interactions[nid]
            return n.summary or n.reference or n.question[:60]
        if nid in graph.entities:
            return graph.entities[nid].name
        if nid in graph.state_nodes:
            return graph.state_nodes[nid].label
        return nid

    relations = []
    for edge in store.out_edges(node_id):
        relations.append(
            {
                "direction": "out",
                "other": edge.target,
                "other_name": display_name(edge.target),
                "label": edge.relation,
                "group": edge.group,
                "strength": edge.strength,
            }
        )
    for edge in store.in_edges(node_id):
        relations.append(
            {
                "direction": "in",
                "other": edge.source,
                "other_name": display_name(edge.source),
                "label": edge.relation,
                "group": edge.group,
                "strength": edge.strength,
            }
        )

    return {"id": node_id, "kind": kind, "node": payload, "relations": relations}
