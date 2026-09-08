"""Build a memory graph from a conversation JSON file.

    python -m scripts.ingest_conversation data/raw/conversation_input.json \
        --conversation-id phase12_demo

Input format - a list of interactions, each with turns::

    [
      {"id": "I_1", "date": "2026-01-15",
       "turns": [{"speaker": "researcher", "text": "..."},
                 {"speaker": "assistant",  "text": "..."}]}
    ]

Also accepts the flatter ``[{"question": ..., "answer": ..., "date": ...}]``.

Because the answers are already present, this runs the pipeline with answer
generation SKIPPED - only extraction runs. That is the right mode for building a
validation corpus: you want to measure the extraction pipeline against a fixed
transcript, not introduce a second variable by regenerating the answers.

The script reports per-turn cost. Those numbers are the first real check on the
bounded-per-turn-cost constraint, which until now has only been estimated.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
from pathlib import Path

from core.config import (
    ANSWER_PROFILE,
    BASELINE_HIERARCHICAL_PROFILE,
    BASELINE_SEMANTIC_PROFILE,
    ENRICHED_PROFILE,
    PRAGMATIC_ONLY_PROFILE,
    RECENCY_ONLY_PROFILE,
    Settings,
)
from core.llm.client import StubLLMClient
from core.llm.embeddings import build_embedder
from core.persistence import JsonConversationRepository
from core.pipeline import TurnPipeline

#: Named profiles selectable from the CLI via ``--profile``.
#: These reproduce the five Task 4.4 conditions without code changes.
NAMED_PROFILES = {
    "default": ANSWER_PROFILE,
    "recency_only": RECENCY_ONLY_PROFILE,
    "baseline_semantic": BASELINE_SEMANTIC_PROFILE,
    "baseline_hierarchical": BASELINE_HIERARCHICAL_PROFILE,
    "pragmatic_only": PRAGMATIC_ONLY_PROFILE,
    "enriched": ENRICHED_PROFILE,
}

logger = logging.getLogger("ingest")


def load_turns(path: Path) -> list[dict]:
    """Normalise either supported input shape into ``{question, answer, date}``."""
    raw = json.loads(path.read_text(encoding="utf-8"))
    turns: list[dict] = []

    for item in raw:
        if "turns" in item:
            user = next(
                (t["text"] for t in item["turns"] if t.get("speaker") != "assistant"), ""
            )
            assistant = next(
                (t["text"] for t in item["turns"] if t.get("speaker") == "assistant"), ""
            )
            turns.append({"question": user, "answer": assistant, "date": item.get("date")})
        else:
            turns.append(
                {
                    "question": item.get("question", ""),
                    "answer": item.get("answer", ""),
                    "date": item.get("date"),
                }
            )
    return [t for t in turns if t["question"] or t["answer"]]


def build_client(settings: Settings):
    """Select the LLM client based on available credentials.

    Priority order:
    1. OpenAI-compatible endpoint (GM_OPENAI_BASE_URL): uses the configured local
       SLM (Ollama, vLLM, LM Studio). This is the path for Phase 4 multi-model
       comparison. Set GM_EXTRACTION_MODEL to the model name (e.g. "mistral").
    2. Anthropic API (ANTHROPIC_API_KEY): the cloud default.
    3. StubLLMClient: offline / plumbing-test fallback, with a loud warning.

    The warning matters: a silent fall-back to the stub produces a graph with
    nodes and no edges, which looks like a classifier failure rather than a
    missing API key.
    """
    if settings.models.openai_base_url:
        from core.llm.client import OpenAICompatClient  # noqa: PLC0415

        logger.info(
            "Using OpenAI-compatible endpoint: %s model=%s",
            settings.models.openai_base_url,
            settings.models.extraction_model,
        )
        return OpenAICompatClient(
            model=settings.models.extraction_model,
            base_url=settings.models.openai_base_url,
            api_key=settings.models.openai_api_key,
        )
    if os.environ.get("ANTHROPIC_API_KEY"):
        from core.llm.client import AnthropicClient  # noqa: PLC0415

        return AnthropicClient(settings.models.extraction_model)
    logger.warning(
        "Neither GM_OPENAI_BASE_URL nor ANTHROPIC_API_KEY is set. Using "
        "StubLLMClient: the graph will have nodes but NO extracted entities, "
        "edges or state nodes. This is a plumbing test, not a real ingest."
    )
    return StubLLMClient()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("--conversation-id", required=True)
    parser.add_argument("--title", default=None)
    parser.add_argument(
        "--no-extract",
        action="store_true",
        help="Only create nodes and embeddings. Null baseline / fast smoke test.",
    )
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument(
        "--profile",
        choices=list(NAMED_PROFILES.keys()),
        default="default",
        help=(
            "Context profile for retrieval during ingestion. "
            "The five named profiles reproduce Task 4.4 ablation conditions. "
            "Default: 'default' (same as 'enriched' / ANSWER_PROFILE)."
        ),
    )
    parser.add_argument(
        "--strategy",
        choices=["multi_call", "combined_call"],
        default=None,
        help="Extraction strategy. Overrides the default in PipelineConfig.",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    settings = Settings()
    settings.answer_profile = NAMED_PROFILES[args.profile]
    if args.strategy is not None:
        settings.pipeline.strategy = args.strategy
    repo = JsonConversationRepository()
    if repo.exists(args.conversation_id):
        if not args.overwrite:
            raise SystemExit(
                f"conversation '{args.conversation_id}' already exists. "
                "Pass --overwrite to replace it."
            )
        repo.delete(args.conversation_id)

    graph = repo.create(args.conversation_id, title=args.title, source=str(args.input))
    pipeline = TurnPipeline(build_client(settings), build_embedder(
        settings.models.embedding_model, settings.models.embedding_dim
    ), settings)

    turns = load_turns(args.input)
    total_calls = total_in = total_out = 0

    for i, turn in enumerate(turns, start=1):
        result = pipeline.process_turn(
            graph,
            turn["question"],
            answer=turn["answer"],
            date=turn["date"],
            extract=not args.no_extract,
        )
        total_calls += result.cost.n_calls
        total_in += result.cost.input_tokens
        total_out += result.cost.output_tokens
        logger.info(
            "%s/%s %s  calls=%d  edges=%d/%d  state=+%d  %s",
            i, len(turns), result.node.id, result.cost.n_calls,
            len(result.node.hierarchical_edges), len(result.node.pragmatic_edges),
            len(result.node.state_node_links.creates),
            f"ERRORS: {result.errors}" if result.errors else "",
        )
        # Save every turn, not just at the end: a long ingest that dies at turn
        # 90 should leave 89 usable turns, not nothing.
        repo.save(graph)

    dangling = graph.dangling_references()
    print("\n--- ingest complete ---")
    print(f"turns:            {len(turns)}")
    print(f"model calls:      {total_calls}  ({total_calls / max(1, len(turns)):.1f} per turn)")
    print(f"tokens in/out:    {total_in} / {total_out}")
    print(f"entities:         {len(graph.entities)}")
    print(f"state nodes:      {len(graph.state_nodes)}")
    if dangling:
        print(f"WARNING dangling references: {dangling}")


if __name__ == "__main__":
    main()
