# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Is

A graph-augmented conversational memory system (thesis research at INESC TEC, supervised by Prof. Davide Carneiro). The system processes multi-turn dialogues, extracts entities and discourse relations via Claude AI, and maintains a dynamic knowledge graph. It extends the baseline architecture from Oliveira (2026) by adding pragmatic edges, named entity nodes, and state nodes (goals, decisions, constraints, open questions).

The design document is `INESCTEC_RESEARCH.md` — consult it for schema decisions, edge-strength rationale, and open questions that Phase 3/4 are meant to settle empirically.

## Commands

### Backend (Python, requires UV)

```bash
uv sync

# Run FastAPI dev server (from project root)
cd main && uvicorn app.backend.main:app --reload
# http://127.0.0.1:8000 — API at /api, frontend SPA at /
```

### Frontend (TypeScript + React + Vite)

```bash
cd main/app/frontend
npm install
npm run dev        # Vite dev server
npm run build      # Production build → backend static dir
npm run typecheck  # Type check only
```

### Scripts

```bash
python -m scripts.ingest_conversation data/raw/conversation.json --conversation-id <id>
python -m scripts.ingest_document papers/doc.pdf --title "Title"
python -m scripts.export_graph_snapshot <conversation_id> --out snapshot.json
```

### Evaluation

```bash
python -m evaluation.run_validation --conversation <id> --gold data/eval_corpora/<id>.json
```

## Architecture

### Strict Layered Dependencies

```
schema  ←  persistence
        ←  llm
        ←  graph
        ←  retrieval  ←  pipeline  ←  app / scripts / evaluation
```

Nothing in `app`, `scripts`, or `evaluation` is imported by `core`. No layer imports from a layer above it.

### Core Modules (`main/core/`)

- **`schema/`** — Domain models with no internal dependencies: `ConversationGraph`, `InteractionNode` (one Q/A pair with edges and epistemic state), `Entity`, `StateNode`, and edge enums. Everything else builds on these.
- **`llm/`** — Anthropic Claude client, embedding models (hashing default, sentence-transformers optional), and prompt templates for each of the 5 extraction tasks.
- **`persistence/`** — JSON-backed repositories for `ConversationGraph` and documents.
- **`graph/`** — In-memory graph store and traversal/expansion queries.
- **`retrieval/`** — Budget-based context assembly combining recency, semantic similarity, graph expansion, state nodes, and RAG document chunks. Also contains `rag/` for PDF chunking and cosine top-k retrieval.
- **`pipeline/`** — `TurnPipeline` in `orchestrator.py` processes one dialogue turn end-to-end. `steps.py` defines the 5 extraction steps (W1–W5).

### Per-Turn Data Flow

1. Assemble context (recency + semantic + graph + state + documents) — budget-bounded
2. Generate answer (LLM call R2) — **on critical path**
3. Create interaction node + embed — **on critical path**
4. Select edge candidates (R1)
5. Run W1–W5 extractions — **deferred** (after answer is returned)
6. Apply extraction results and commit to graph

**The 5 extraction steps:**

| Step | Purpose                                                                                                                                   | Blocks                         |
| ---- | ----------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------ |
| W1   | Entity extraction + speech act classification                                                                                             | W2, W3 depend on W1's entities |
| W2   | Hierarchical edge classification (subcase / supercase / same_level)                                                                       | Independent of W3              |
| W3   | Pragmatic edge classification (revises / contradicts / resolves / depends_on / references) + writes epistemic_status back to target nodes | Independent of W2              |
| W4   | State node extraction/merge — creates/updates Goal, Decision, Constraint, OpenQuestion nodes                                              | Independent                    |
| W5   | Turn summary + reference string for compression tiers                                                                                     | Independent                    |

W2 and W3 are independent axes on the same candidate pairs — a node pair can have both a hierarchical and a pragmatic edge, either, or neither. `no_relation` is never stored.

### Schema Highlights

**Epistemic status** on `InteractionNode` is write-time derived from pragmatic edges: `revises` → superseded, `resolves` → resolved, `contradicts` → contested. Default at creation depends on `speech_act`: `open` for `factual_question`/`clarification_request`, `resolved` for everything else.

**State nodes** have type-specific lifecycle statuses with terminal states enforced in `apply_w4` (terminal states block further LLM-proposed updates).

**Compression tiers** for context injection (greedy first-fit against token budget): Tier 1 = full Q+A, Tier 2 = stored summary (W5), Tier 3 = live-rendered state-node/entity reference or fallback to stored `reference` string (W5).

### Configuration (`main/core/config.py`)

Single source of truth, with provenance annotations: `[thesis]` = empirical baseline, `[provisional]` = Phase 4 sweep target, `[engineering]` = implementation choice.

Key knobs:

- `ANSWER_PROFILE` / `EDGE_PROFILE` — context budget sizes (items + graph fraction)
- `PipelineConfig.strategy` — `"multi_call"` (5 task-scoped calls) vs `"combined_call"`
- `PipelineConfig.best_effort` — `True` means failed extraction steps don't drop the whole turn

Environment variable overrides:

- `GM_DATA_ROOT` — data directory (default: `main/data/`)
- `GM_ANSWER_MODEL` / `GM_EXTRACTION_MODEL` — Claude model IDs (default: `claude-sonnet-4-6`)
- `GM_EMBEDDING_MODEL` — `"hashing"` (default) or `"sentence-transformers"`
- `GM_ENABLE_CHAT=1` — enables the `/api/chat/turn` endpoint (disabled by default; single-process only, per-conversation lock)

### App Layer (`main/app/`)

- **Backend** — FastAPI with CORS. Key routes: `/api/conversations`, `/api/graph/{id}`, `/api/documents`, `/api/chat/turn` (gated), `/api/health`. Frontend SPA served from `/static`.
- **Frontend** — React 18 + TypeScript + Vite. D3.js for graph visualization, Zustand for local state, TanStack Query for server state.

### Known Gaps (do not fix without thesis context)

1. W2–W5 run sequentially in the current implementation; the design intends them to run in parallel.
2. Live chat concurrency is single-process only (per-conversation asyncio lock).
3. Compression tier selection does not yet consider `epistemic_status` or `recurrence_count` when choosing how hard to compress a node.
