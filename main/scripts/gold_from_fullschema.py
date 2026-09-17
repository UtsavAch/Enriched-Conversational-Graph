"""Convert a "full schema" ground truth file into the flat GoldAnnotation format.

    python -m scripts.gold_from_fullschema ../conversations/rest_api/ground_truth.json \
        --conversation-id rest_api --out data/eval_corpora/rest_api.json

Ground truth for a corpus is drafted in the same shape as the Section 4 worked
example in INESCTEC_RESEARCH.md - a dict of interaction_nodes (with inline
edges and state_node_links), entities, and state_nodes - because that is the
shape an LLM/human naturally audits against the schema doc. `run_validation.py`
instead consumes the flat `GoldAnnotation` shape (entities/relations/
state_nodes/probes) defined in `evaluation/annotation.py`, so the metrics never
need to know about the full-schema representation.

This script is the one place that translates between the two, so every corpus
built the same way (see the Phase 3 plan) goes through the same conversion
instead of being hand-transcribed per corpus.

`probes` are never present in the full-schema ground truth (they are authored
by hand afterwards, against the flat file this script produces) - existing
probes in an `--out` file that already exists are preserved across re-runs.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def convert(fullschema: dict, conversation_id: str) -> dict:
    entities = [
        {"turn_id": turn_id, "name": e["name"], "type": e.get("type", "")}
        for e in fullschema.get("entities", {}).values()
        for turn_id in e.get("mentioned_in", [])
    ]

    relations = [
        {"source": node_id, "target": target, "relation": label}
        for node_id, node in fullschema.get("interaction_nodes", {}).items()
        for label_list in node.get("edges", {}).values()
        for target, label in label_list
    ]

    state_nodes = [
        {"type": sn["type"], "label": sn["label"], "status": sn.get("status", "active")}
        for sn in fullschema.get("state_nodes", {}).values()
    ]

    return {
        "conversation_id": conversation_id,
        "entities": entities,
        "relations": relations,
        "state_nodes": state_nodes,
        "probes": [],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("fullschema", type=Path, help="Path to the full-schema ground_truth.json")
    parser.add_argument("--conversation-id", required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    fullschema = json.loads(args.fullschema.read_text(encoding="utf-8"))
    out_data = convert(fullschema, args.conversation_id)

    if args.out.exists():
        existing = json.loads(args.out.read_text(encoding="utf-8"))
        out_data["probes"] = existing.get("probes", [])

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(out_data, indent=2, ensure_ascii=False), encoding="utf-8")

    print(
        f"wrote {args.out}: {len(out_data['entities'])} entities, "
        f"{len(out_data['relations'])} relations, {len(out_data['state_nodes'])} state_nodes, "
        f"{len(out_data['probes'])} probes (preserved)"
    )


if __name__ == "__main__":
    main()
