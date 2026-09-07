"""Ground-truth annotation format and loader for Phase 3 validation.

The Phase 3 readiness checklist says the missing pieces are "ground-truth entity
annotations on the chosen corpus" and "a validation corpus with genuine topic
development". This module defines the file format for the former, so annotation
can start before any of the metric definitions are final.

Format (one JSON file per conversation, under ``data/eval_corpora``)::

    {
      "conversation_id": "support_dialog_01",
      "entities":  [ {"turn_id": "N_1", "name": "INESC TEC", "type": "organization"} ],
      "relations": [ {"source": "N_3", "target": "N_2", "relation": "subcase"} ],
      "state_nodes": [ {"type": "decision", "label": "...", "status": "active"} ],
      "probes": [ {"probe_id": "p1", "question": "...", "target": "SN_3",
                   "expected_any": ["five"], "forbidden_any": ["two"]} ]
    }

Deliberately a flat, hand-editable JSON file rather than a database or a
labelling-tool export. Phase 3 validation is a few hundred annotations done by
one person; the cost of a tool exceeds the cost of the annotation.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from evaluation.metrics.consistency import ConsistencyProbe
from evaluation.metrics.entity_prf import EntityRef
from evaluation.metrics.relation_accuracy import RelationRef
from evaluation.metrics.state_node_merge import StateNodeRef


@dataclass
class GoldAnnotation:
    """Hand-annotated ground truth for one conversation."""

    conversation_id: str
    entities: list[EntityRef] = field(default_factory=list)
    relations: list[RelationRef] = field(default_factory=list)
    state_nodes: list[StateNodeRef] = field(default_factory=list)
    probes: list[ConsistencyProbe] = field(default_factory=list)

    @classmethod
    def load(cls, path: Path | str) -> "GoldAnnotation":
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls(
            conversation_id=raw["conversation_id"],
            entities=[EntityRef(**e) for e in raw.get("entities", [])],
            relations=[RelationRef(**r) for r in raw.get("relations", [])],
            state_nodes=[StateNodeRef(**s) for s in raw.get("state_nodes", [])],
            probes=[ConsistencyProbe(**p) for p in raw.get("probes", [])],
        )

    @staticmethod
    def template(conversation_id: str) -> dict:
        """An empty annotation file to start from, with the shape documented."""
        return {
            "conversation_id": conversation_id,
            "_comment": "Fill in ground truth by hand. See evaluation/annotation.py.",
            "entities": [{"turn_id": "N_1", "name": "", "type": "organization"}],
            "relations": [{"source": "N_2", "target": "N_1", "relation": "depends_on"}],
            "state_nodes": [{"type": "decision", "label": "", "status": "active"}],
            "probes": [
                {
                    "probe_id": "p1",
                    "question": "",
                    "target": "SN_1",
                    "expected_any": [],
                    "forbidden_any": [],
                    "valid_from_turn": 0,
                }
            ],
        }


def extract_predictions(graph) -> dict:
    """Pull predictions out of a built graph, in the metrics' input format.

    Keeping this here rather than in the metrics modules preserves an important
    property: the metrics never import the pipeline or the schema, so they can be
    run over annotations produced by hand, by this pipeline, or by a competing
    system, without modification.
    """
    entities = [
        EntityRef(turn_id=turn_id, name=e.name, type=e.type.value)
        for e in graph.entities.values()
        for turn_id in e.mentioned_in
    ]
    relations = [
        RelationRef(source=n.id, target=edge.target, relation=edge.relation.value)
        for n in graph.interactions.values()
        for edge in list(n.hierarchical_edges) + list(n.pragmatic_edges)
    ]
    state_nodes = [
        StateNodeRef(type=sn.type.value, label=sn.label, status=sn.status.value)
        for sn in graph.state_nodes.values()
    ]
    return {"entities": entities, "relations": relations, "state_nodes": state_nodes}
