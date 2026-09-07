"""Phase 3.1 entrypoint: run the pipeline on a corpus and score it.

    python -m evaluation.run_validation --conversation support_01 \
        --gold data/eval_corpora/support_01.json

Produces a JSON report under ``evaluation/reports/``. That report is the input
to the Phase 3 deliverable ("a short validation report with error analysis and
examples of failure modes, before any quantitative evaluation") - note the
ordering in the workplan: error analysis first, numbers second. The report
therefore leads with examples, not with an F1 table.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from core.persistence import JsonConversationRepository
from evaluation.annotation import GoldAnnotation, extract_predictions
from evaluation.metrics import (
    entity_prf,
    error_examples,
    evaluate_state_nodes,
    per_relation_prf,
    resolution_linking_accuracy,
)
from evaluation.metrics.relation_accuracy import confusion_matrix

REPORTS_DIR = Path(__file__).resolve().parent / "reports"


def validate(conversation_id: str, gold_path: Path, repo=None) -> dict:
    """Score one already-built conversation against its gold annotation."""
    repo = repo or JsonConversationRepository()
    graph = repo.load(conversation_id)
    gold = GoldAnnotation.load(gold_path)
    pred = extract_predictions(graph)

    return {
        "conversation_id": conversation_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "schema_version": graph.meta.schema_version,
        "corpus_size": {
            "turns": len(graph.interactions),
            "entities": len(graph.entities),
            "state_nodes": len(graph.state_nodes),
        },
        # Error analysis first - this is what Phase 3 is actually for.
        "error_analysis": {
            "entities": error_examples(pred["entities"], gold.entities),
            "relation_confusion": confusion_matrix(pred["relations"], gold.relations),
            "state_nodes": evaluate_state_nodes(
                pred["state_nodes"], gold.state_nodes
            ).as_dict(),
        },
        "metrics": {
            "entity_prf_normalised": entity_prf(pred["entities"], gold.entities).as_dict(),
            "entity_prf_typed": entity_prf(
                pred["entities"], gold.entities, criterion="typed"
            ).as_dict(),
            "relations": per_relation_prf(pred["relations"], gold.relations),
            "resolves_linking": resolution_linking_accuracy(
                pred["relations"], gold.relations
            ),
        },
        "integrity": {"dangling_references": graph.dangling_references()},
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--conversation", required=True)
    parser.add_argument("--gold", required=True, type=Path)
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()

    report = validate(args.conversation, args.gold)
    out = args.out or REPORTS_DIR / f"{args.conversation}_validation.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print(json.dumps(report["metrics"], indent=2))
    print(f"\nfull report (including error analysis) -> {out}")


if __name__ == "__main__":
    main()
