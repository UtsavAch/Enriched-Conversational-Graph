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
Either shape may use ``"timestamp"`` instead of ``"date"`` (this is what
``conversation.json``, exported by the persistence layer, uses) - both are
read, ``"timestamp"`` taking precedence if a record has both.

Because the answers are already present, this runs the pipeline with answer
generation SKIPPED - only extraction runs. That is the right mode for building a
validation corpus: you want to measure the extraction pipeline against a fixed
transcript, not introduce a second variable by regenerating the answers.

The script reports per-turn cost. Those numbers are the first real check on the
bounded-per-turn-cost constraint, which until now has only been estimated.

Resuming a stalled run
-----------------------
A long ingest against a slow local model can stall or need stopping partway
(see evaluation_report.md section 9). Pass ``--resume`` instead of
``--overwrite`` to continue an existing conversation from wherever it left
off, rather than reprocessing turns 1..k for nothing:

    python -m scripts.ingest_conversation data/raw/conversation_input.json \
        --conversation-id phase12_demo --resume

Safe to pass even when the conversation doesn't exist yet (starts fresh) or
is already fully ingested (no-ops). Before resuming, the already-stored
turns' questions are checked against the same positions in ``input`` and the
run aborts if they don't match - resuming against an edited or different
input file would otherwise silently misalign turn numbering against
existing edges/state-node links, which reference nodes by id, not position.
"""

from __future__ import annotations

from dotenv import load_dotenv
load_dotenv()

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
    """Normalise either supported input shape into ``{question, answer, timestamp}``."""
    raw = json.loads(path.read_text(encoding="utf-8"))
    turns: list[dict] = []

    for item in raw:
        timestamp = item.get("timestamp") or item.get("date")
        if "turns" in item:
            user = next(
                (t["text"] for t in item["turns"] if t.get("speaker") != "assistant"), ""
            )
            assistant = next(
                (t["text"] for t in item["turns"] if t.get("speaker") == "assistant"), ""
            )
            turns.append({"question": user, "answer": assistant, "timestamp": timestamp})
        else:
            turns.append(
                {
                    "question": item.get("question", ""),
                    "answer": item.get("answer", ""),
                    "timestamp": timestamp,
                }
            )
    return [t for t in turns if t["question"] or t["answer"]]


def check_resume_prefix(graph, turns: list[dict]) -> None:
    """Abort loudly if ``graph``'s existing turns don't match ``turns`` at the same positions.

    The only thing that makes resuming safe: turn *position* in ``input`` must
    still mean the same turn as it did in the earlier run, because every edge,
    citation and state-node link in the stored graph references nodes by id
    (``N_7``, ...), not by re-deriving position from the input file. A silent
    mismatch here would look fine and corrupt every reference downstream.
    """
    existing = graph.ordered_interactions()
    if len(existing) > len(turns):
        raise SystemExit(
            f"cannot resume: stored conversation has {len(existing)} turns but the "
            f"input file only has {len(turns)}. Wrong input file for this conversation?"
        )
    for node, turn in zip(existing, turns):
        if node.question.strip() != turn["question"].strip():
            raise SystemExit(
                f"cannot resume: stored turn {node.id} question does not match "
                f"the input file at the same position. Wrong or edited input file - "
                f"use --overwrite if that's intentional."
            )


def build_client(settings: Settings):
    """Select the LLM client based on available credentials.

    Priority order:
    1. OpenAI-compatible endpoint (GM_OPENAI_BASE_URL): local SLM (Ollama,
       vLLM, LM Studio) or a free-tier cloud provider (Groq, etc.). Set
       GM_EXTRACTION_MODEL to the model name.
    2. Anthropic API (ANTHROPIC_API_KEY): the cloud default.
    3. StubLLMClient: offline / plumbing-test fallback, with a loud warning.

    The warning matters: a silent fall-back to the stub produces a graph with
    nodes and no edges, which looks like a classifier failure rather than a
    missing API key.

    If GM_RPM_LIMIT and/or GM_TPM_LIMIT are set, whichever client above gets
    wrapped in RateLimitedClient - see core/llm/client.py for why (two
    different free-tier providers, two different limit shapes, both hit
    within a session). Unset by default, so this is a no-op unless configured.
    """
    if settings.models.openai_base_url:
        from core.llm.client import OpenAICompatClient  # noqa: PLC0415

        logger.info(
            "Using OpenAI-compatible endpoint: %s model=%s",
            settings.models.openai_base_url,
            settings.models.extraction_model,
        )
        client = OpenAICompatClient(
            model=settings.models.extraction_model,
            base_url=settings.models.openai_base_url,
            api_key=settings.models.openai_api_key,
        )
    elif os.environ.get("ANTHROPIC_API_KEY"):
        from core.llm.client import AnthropicClient  # noqa: PLC0415

        client = AnthropicClient(settings.models.extraction_model)
    else:
        logger.warning(
            "Neither GM_OPENAI_BASE_URL nor ANTHROPIC_API_KEY is set. Using "
            "StubLLMClient: the graph will have nodes but NO extracted entities, "
            "edges or state nodes. This is a plumbing test, not a real ingest."
        )
        client = StubLLMClient()

    if settings.models.requests_per_minute or settings.models.tokens_per_minute:
        from core.llm.client import RateLimitedClient  # noqa: PLC0415

        logger.info(
            "Rate-limiting enabled: rpm=%s tpm=%s",
            settings.models.requests_per_minute, settings.models.tokens_per_minute,
        )
        client = RateLimitedClient(
            client,
            requests_per_minute=settings.models.requests_per_minute,
            tokens_per_minute=settings.models.tokens_per_minute,
        )
    return client


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
    parser.add_argument(
        "--overwrite", action="store_true", help="Discard an existing conversation, start over."
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help=(
            "Continue an existing conversation from its current turn count instead of "
            "starting over. See the module docstring. Mutually exclusive with --overwrite."
        ),
    )
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
    parser.add_argument(
        "--domain-config",
        type=Path,
        default=None,
        help=(
            "JSON file of {type_name: description} entity types this domain adds on "
            "top of the built-in default set (core.schema.enums.DEFAULT_ENTITY_TYPES). "
            "Stored on the conversation's meta, so it's fixed for this conversation's "
            "lifetime. Omit to use the default set only - existing corpora need no "
            "changes. Draft one with scripts/discover_domain_config.py."
        ),
    )
    args = parser.parse_args()

    if args.overwrite and args.resume:
        raise SystemExit("--overwrite and --resume are mutually exclusive.")

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    settings = Settings()
    settings.answer_profile = NAMED_PROFILES[args.profile]
    if args.strategy is not None:
        settings.pipeline.strategy = args.strategy
    repo = JsonConversationRepository()
    turns = load_turns(args.input)

    if repo.exists(args.conversation_id):
        if args.overwrite:
            repo.delete(args.conversation_id)
            graph = repo.create(args.conversation_id, title=args.title, source=str(args.input))
        elif args.resume:
            graph = repo.load(args.conversation_id)
            check_resume_prefix(graph, turns)
            logger.info(
                "resuming '%s': %d/%d turns already done",
                args.conversation_id, len(graph.interactions), len(turns),
            )
        else:
            raise SystemExit(
                f"conversation '{args.conversation_id}' already exists. "
                "Pass --overwrite to replace it, or --resume to continue it."
            )
    else:
        if args.resume:
            logger.info("no existing conversation '%s' - starting fresh", args.conversation_id)
        graph = repo.create(args.conversation_id, title=args.title, source=str(args.input))

    if args.domain_config:
        graph.meta.entity_type_vocab = json.loads(
            args.domain_config.read_text(encoding="utf-8")
        )
        repo.save(graph)
    pipeline = TurnPipeline(build_client(settings), build_embedder(
        settings.models.embedding_model, settings.models.embedding_dim,
        api_key=settings.models.gemini_api_key,
    ), settings)

    already_done = len(graph.interactions)
    remaining = turns[already_done:]
    total_calls = total_in = total_out = 0

    if not remaining:
        print(f"'{args.conversation_id}' already has all {len(turns)} turns. Nothing to do.")
        return

    for i, turn in enumerate(remaining, start=already_done + 1):
        result = pipeline.process_turn(
            graph,
            turn["question"],
            answer=turn["answer"],
            timestamp=turn["timestamp"],
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
        # 90 should leave 89 usable turns, not nothing - and be resumable from there.
        repo.save(graph)

    dangling = graph.dangling_references()
    print("\n--- ingest complete ---")
    print(f"turns this run:   {len(remaining)}  (total now {len(graph.interactions)}/{len(turns)})")
    print(f"model calls:      {total_calls}  ({total_calls / max(1, len(remaining)):.1f} per turn)")
    print(f"tokens in/out:    {total_in} / {total_out}")
    print(f"entities:         {len(graph.entities)}")
    print(f"state nodes:      {len(graph.state_nodes)}")
    if dangling:
        print(f"WARNING dangling references: {dangling}")


if __name__ == "__main__":
    main()
