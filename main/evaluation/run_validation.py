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
    aggregate,
    entity_prf,
    error_examples,
    evaluate_state_nodes,
    judge_consistency,
    per_relation_prf,
    resolution_linking_accuracy,
    score_keyword_probe,
    should_judge,
)
from evaluation.metrics.relation_accuracy import confusion_matrix

REPORTS_DIR = Path(__file__).resolve().parent / "reports"


def run_probes(conversation_id: str, gold: GoldAnnotation, *, use_judge: bool, repo=None) -> dict:
    """Ask each probe's question against the built graph and score the answer.

    Runs the real answer-generation pipeline (not the stored corpus answers -
    those don't exist for a fresh question), against a freshly-loaded copy of
    the graph so probing never mutates or persists into the corpus itself.
    Deferred imports: this is the only entrypoint that needs a live LLM
    client, so `run_validation.py`'s no-argument metrics path stays usable
    with no model configured at all.
    """
    from core.config import Settings  # noqa: PLC0415
    from core.llm.embeddings import build_embedder  # noqa: PLC0415
    from core.pipeline import TurnPipeline  # noqa: PLC0415
    from scripts.ingest_conversation import build_client  # noqa: PLC0415

    if not gold.probes:
        return {"n_probes": 0, "keyword": aggregate([]), "judge": []}

    repo = repo or JsonConversationRepository()
    settings = Settings()
    client = build_client(settings)
    embedder = build_embedder(
        settings.models.embedding_model, settings.models.embedding_dim,
        api_key=settings.models.gemini_api_key,
    )
    pipeline = TurnPipeline(client, embedder, settings)

    keyword_outcomes = []
    judge_verdicts = []
    for probe in gold.probes:
        graph = repo.load(conversation_id)  # fresh copy per probe, never saved back
        result = pipeline.process_turn(graph, probe.question, extract=False)
        outcome = score_keyword_probe(probe, result.node.answer)
        keyword_outcomes.append(outcome)

        if use_judge and should_judge(outcome) and probe.decision_text:
            verdict = judge_consistency(
                client,
                probe,
                probe.decision_text,
                result.node.answer,
                model_name=settings.models.extraction_model,
            )
            judge_verdicts.append(verdict.as_dict())

    return {
        "n_probes": len(gold.probes),
        "keyword": aggregate(keyword_outcomes),
        "judge": judge_verdicts,
    }


def validate(
    conversation_id: str, gold_path: Path, repo=None, *, run_probes_flag: bool = False,
    use_judge: bool = False,
) -> dict:
    """Score one already-built conversation against its gold annotation."""
    repo = repo or JsonConversationRepository()
    graph = repo.load(conversation_id)
    gold = GoldAnnotation.load(gold_path)
    pred = extract_predictions(graph)

    report = {
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

    if run_probes_flag:
        report["consistency"] = run_probes(conversation_id, gold, use_judge=use_judge, repo=repo)

    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--conversation", required=True)
    parser.add_argument("--gold", required=True, type=Path)
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument(
        "--profile",
        choices=[
            "default",
            "recency_only",
            "baseline_semantic",
            "baseline_hierarchical",
            "pragmatic_only",
            "enriched",
        ],
        default=None,
        help=(
            "Context profile used during ingestion, recorded in the report for "
            "traceability. Does not re-run the pipeline; use "
            "scripts/ingest_conversation.py --profile to build under a specific profile."
        ),
    )
    parser.add_argument(
        "--run-probes",
        action="store_true",
        help=(
            "Also ask each gold probe's question against the built graph and score "
            "the answer with the keyword consistency check (workplan 4.3). Requires "
            "a configured LLM client (GM_OPENAI_BASE_URL or ANTHROPIC_API_KEY) - "
            "this is the one part of validation that makes live model calls."
        ),
    )
    parser.add_argument(
        "--judge",
        action="store_true",
        help=(
            "With --run-probes, also escalate any keyword-probe FAILURE to an "
            "LLM judge (llm_judge.py) - never re-judges a keyword pass, per "
            "consistency.py's rule. No-op without --run-probes."
        ),
    )
    args = parser.parse_args()

    report = validate(
        args.conversation, args.gold, run_probes_flag=args.run_probes, use_judge=args.judge
    )
    if args.profile:
        report["profile"] = args.profile
    out = args.out or REPORTS_DIR / f"{args.conversation}_validation.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print(json.dumps(report["metrics"], indent=2))
    if "consistency" in report:
        print(json.dumps(report["consistency"], indent=2))
    print(f"\nfull report (including error analysis) -> {out}")


if __name__ == "__main__":
    main()
