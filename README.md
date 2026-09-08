## Graph Augmented Conversational memory

The system processes multi-turn dialogues, extracts entities and discourse relations via Claude AI, and maintains a dynamic knowledge graph. It extends the previous baseline architecture by adding pragmatic edges, named entity nodes, and state nodes (goals, decisions, constraints, open questions).

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
# With a specific context profile (recency_only | baseline_semantic | baseline_hierarchical | pragmatic_only | enriched)
python -m scripts.ingest_conversation data/raw/conversation.json --conversation-id <id> --profile enriched
# With combined LLM call instead of 5 separate calls
python -m scripts.ingest_conversation data/raw/conversation.json --conversation-id <id> --strategy combined_call
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
3. Create interaction node — **on critical path**
4. Select edge candidates (R1)
5. Run W1–W5 extractions — **deferred** (after answer is returned), **three-wave concurrent**
6. Apply extraction results and commit to graph

**Three-wave concurrent extraction (Section 5.7):**

| Wave | Tasks              | Starts when                      |
| ---- | ------------------ | -------------------------------- |
| 1    | EMBED + W1 + W5    | Immediately (need only raw turn) |
| 2    | W4                 | After EMBED completes            |
| 3    | W2 + W3 (parallel) | After both EMBED and W1 finish   |

Wall-clock cost is the slowest wave, not the sum of all calls.

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

**Epistemic status** on `InteractionNode` is write-time derived from pragmatic edges: `revises` → superseded (always wins regardless of current status), `resolves` → resolved (unless target is already superseded), `contradicts` → contested (unless target is already superseded). Default at creation depends on `speech_act`: `open` for `factual_question`/`clarification_request`, `resolved` for everything else.

**State nodes** have type-specific lifecycle statuses with terminal states enforced in `apply_w4` (terminal states block further LLM-proposed updates):

| Type            | Valid statuses                | Terminal            |
| --------------- | ----------------------------- | ------------------- |
| `goal`          | active → achieved / abandoned | achieved, abandoned |
| `decision`      | active → revised → reverted   | reverted            |
| `constraint`    | active → revised → lifted     | lifted              |
| `open_question` | open → resolved               | resolved            |

**Compression tiers** for context injection (greedy first-fit against token budget): Tier 1 = full Q+A, Tier 2 = stored summary (W5), Tier 3 = live-rendered state-node/entity reference or fallback to stored `reference` string (W5).

### Configuration (`main/core/config.py`)

Single source of truth, with provenance annotations: `[thesis]` = empirical baseline, `[provisional]` = Phase 4 sweep target, `[engineering]` = implementation choice.

Key knobs:

- `ANSWER_PROFILE` / `EDGE_PROFILE` — context budget sizes (items + graph fraction)
- Five named comparison profiles for ablation (Section 5.5 Task 4.4): `RECENCY_ONLY`, `BASELINE_SEMANTIC`, `BASELINE_HIERARCHICAL`, `PRAGMATIC_ONLY`, `ENRICHED`
- `PipelineConfig.strategy` — `"multi_call"` (5 task-scoped calls, 3-wave concurrent) vs `"combined_call"` (single call, all W1–W5)
- `PipelineConfig.best_effort` — `True` means failed extraction steps don't drop the whole turn

Environment variable overrides:

- `GM_DATA_ROOT` — data directory (default: `main/data/`)
- `GM_OPENAI_BASE_URL` — OpenAI-compatible endpoint base URL (Ollama, vLLM, LM Studio); takes priority over `ANTHROPIC_API_KEY`
- `GM_OPENAI_API_KEY` — API key for OpenAI-compatible endpoint (default: `"ollama"`)
- `ANTHROPIC_API_KEY` — Anthropic Claude API key; used if `GM_OPENAI_BASE_URL` is not set
- `GM_ANSWER_MODEL` / `GM_EXTRACTION_MODEL` — model IDs (default: `claude-sonnet-4-6`)
- `GM_EMBEDDING_MODEL` — `"hashing"` (default) or `"sentence-transformers"`
- `GM_ENABLE_CHAT=1` — enables the `/api/chat/turn` endpoint (disabled by default; single-process only, per-conversation threading lock)

### App Layer (`main/app/`)

- **Backend** — FastAPI with CORS. Key routes: `/api/conversations`, `/api/graph/{id}`, `/api/documents`, `/api/chat/turn` (gated), `/api/health`. Frontend SPA served from `/static`.
- **Frontend** — React 18 + TypeScript + Vite. D3.js for graph visualization, Zustand for local state, TanStack Query for server state.

### Known Gaps (do not fix without thesis context)

1. Compression tier selection uses slot-type heuristic (FULL/SUMMARY per layer) rather than greedy first-fit against a real token budget (Section 3.6). Deferred to Phase 4.
2. Live chat concurrency is single-process only (per-conversation threading lock; does not survive multiple Uvicorn workers).
3. Compression does not yet weight nodes by `epistemic_status` or `recurrence_count` (e.g. compress superseded nodes harder, protect high-recurrence nodes). Deferred to Phase 4.
