"""Export a conversation as a standalone JSON view model.

    python -m scripts.export_graph_snapshot phase12_demo --out snapshot.json

Two uses:

* frontend fixtures - drop the output into a static page and the visualisation
  works with no backend running, which is what you want for a demo on a laptop
  with no network.
* thesis figures - the exported edge counts and component structure are the
  numbers you would quote when describing a built graph.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.backend.view_model import build_graph_view
from core.persistence import JsonConversationRepository


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("conversation_id")
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()

    graph = JsonConversationRepository().load(args.conversation_id)
    view = build_graph_view(graph)

    out = args.out or Path(f"{args.conversation_id}_snapshot.json")
    out.write_text(json.dumps(view, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"wrote {out}")
    print(json.dumps(view["stats"], indent=2))


if __name__ == "__main__":
    main()
