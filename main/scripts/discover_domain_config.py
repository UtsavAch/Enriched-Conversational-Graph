"""Draft a domain-specific entity-type config from a conversation's transcript.

    python -m scripts.discover_domain_config ../conversations/rest_api/corpus.json \
        --out ../conversations/rest_api/domain_config.json

One LLM pass over the transcript proposes entity types the built-in default
set (``core.schema.enums.DEFAULT_ENTITY_TYPES``) doesn't cover - e.g. "resource"
and "endpoint" for a REST API design conversation - instead of hand-writing
them the way ``conversations/rest_api/ground_truth.json``'s free-text
``schema_note`` currently does. See ``evaluation_report.md`` section 8 for the
design this implements.

This NEVER writes silently into a live domain config - it only ever produces a
draft for a human to read, edit if needed, and then pass to
``scripts.ingest_conversation --domain-config``. Review before use.
"""

from __future__ import annotations

from dotenv import load_dotenv

load_dotenv()

import argparse
import json
from pathlib import Path

from core.config import Settings
from core.llm.client import parse_json_response
from core.llm.prompts import prompts
from core.schema.enums import DEFAULT_ENTITY_TYPES
from scripts.ingest_conversation import build_client, load_turns

#: Cap on turns sampled into the discovery prompt, so a long corpus still
#: makes one bounded-cost call rather than one proportional to its length.
MAX_SAMPLE_TURNS = 40


def render_transcript(turns: list[dict], limit: int = MAX_SAMPLE_TURNS) -> str:
    sample = turns[:limit]
    lines = [f"Q: {t['question']}\nA: {t['answer']}" for t in sample]
    text = "\n\n".join(lines)
    if len(turns) > limit:
        text += f"\n\n[... {len(turns) - limit} further turns omitted from this sample ...]"
    return text


def discover(turns: list[dict], client) -> dict:
    default_types = "\n".join(f"  - {name}: {desc}" for name, desc in DEFAULT_ENTITY_TYPES.items())
    system, user = prompts.render(
        "domain_discovery",
        transcript=render_transcript(turns),
        default_types=default_types,
    )
    response = client.complete(system=system, user=user, max_tokens=512, temperature=0.0)
    payload = parse_json_response(response.text)
    return {
        "types": {str(k): str(v) for k, v in (payload.get("types") or {}).items()},
        "rationale": payload.get("rationale", ""),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="Conversation JSON, same format ingest takes.")
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()

    settings = Settings()
    client = build_client(settings)
    turns = load_turns(args.input)

    draft = discover(turns, client)

    print(f"Rationale: {draft['rationale']}\n")
    print("Proposed types:")
    for name, desc in draft["types"].items():
        print(f"  {name}: {desc}")

    if not draft["types"]:
        print("\n(nothing proposed - default set covers this transcript)")
        return

    out = args.out or args.input.with_name("domain_config.json")
    out.write_text(json.dumps(draft["types"], indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nDRAFT written to {out} - review before passing to --domain-config.")


if __name__ == "__main__":
    main()
