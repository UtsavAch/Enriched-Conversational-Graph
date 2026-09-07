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

from core.config import Settings
from core.llm.client import StubLLMClient
from core.llm.embeddings import build_embedder
from core.persistence import JsonConversationRepository
from core.pipeline import TurnPipeline

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
    """Real client if a key is set, stub otherwise - with a loud warning.

    The warning matters: a silent fall back to the stub produces a graph with
    nodes and no edges, which looks like a classifier failure rather than a
    missing API key. That is an hour of confused debugging waiting to happen.
    """
    if os.environ.get("ANTHROPIC_API_KEY"):
        from core.llm.client import AnthropicClient  # noqa: PLC0415

        return AnthropicClient(settings.models.extraction_model)
    logger.warning(
        "ANTHROPIC_API_KEY is not set. Using StubLLMClient: the graph will have "
        "nodes but NO extracted entities, edges or state nodes. This is a "
        "plumbing test, not a real ingest."
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
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    settings = Settings()
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
