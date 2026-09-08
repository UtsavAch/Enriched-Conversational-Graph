# Consistency Report: Implementation vs. INESCTEC_RESEARCH.md

This document tracks every divergence between the implementation and the Phase 1-2 research
report. Items are either **resolved** (fully fixed) or **remaining** (known, documented gap).

---

## Resolved Items

### 1. SLM / Multi-Provider Support

**Was**: Only `AnthropicClient` and `StubLLMClient` implemented. No path to local SLMs.

**Fixed**: `OpenAICompatClient` added to `core/llm/client.py`. Any OpenAI-compatible endpoint
(Ollama, vLLM, LM Studio) is now selectable by setting `GM_OPENAI_BASE_URL`. Priority order
in both `scripts/ingest_conversation.py` and `app/backend/dependencies.py`:
`GM_OPENAI_BASE_URL` → `ANTHROPIC_API_KEY` → `StubLLMClient` fallback.

---

### 2. State Node Status Schema

**Was**: Status values diverged from the research doc (`superseded` instead of `reverted`,
`satisfied`/`violated` instead of `lifted`, `active` for open questions instead of `open`).

**Fixed**: `core/schema/enums.py` now defines exactly the research doc's lifecycle:

| Type            | Valid statuses              | Terminal            |
| --------------- | --------------------------- | ------------------- |
| `goal`          | active, achieved, abandoned | achieved, abandoned |
| `decision`      | active, revised, reverted   | reverted            |
| `constraint`    | active, revised, lifted     | lifted              |
| `open_question` | open, resolved              | resolved            |

`VALID_STATUSES_BY_TYPE`, `TERMINAL_STATUSES_BY_TYPE`, and `DEFAULT_STATUS_BY_TYPE` dicts
enforce these at parse time. `StateNode.initial_status()` static method returns the correct
starting status per type. `core/schema/state_node.py` uses a `model_validator(mode="before")`
to set the correct default (OPEN for open_question, ACTIVE for the rest) when status is None.

---

### 3. Comparison Profiles (Task 4.4)

**Was**: No named profiles, no `r_pragmatic` field.

**Fixed**: `core/config.py` now defines all five ablation profiles from Section 5.5:
`RECENCY_ONLY_PROFILE`, `BASELINE_SEMANTIC_PROFILE`, `BASELINE_HIERARCHICAL_PROFILE`,
`PRAGMATIC_ONLY_PROFILE`, `ENRICHED_PROFILE`. `ContextProfile` has `r_pragmatic: float | None`,
`compress: bool`, and `count_retrieval: bool`. Selectable via `--profile` in
`scripts/ingest_conversation.py` and recorded in `evaluation/run_validation.py` output.

---

### 4. Entity-Anchored Retrieval

**Was**: `k_entity` existed on `ContextProfile` but was never used.

**Fixed**: `core/retrieval/context_assembly.py` now implements entity-anchored entry points
(Step 2b in the Section 5.5 pseudocode): for each seed entity, `entity_registry[eid].mentioned_in`
is collected and the k_entity most recent are included as entry points. The `assemble()` method
accepts `seed_entity_ids` (optional; defaults to a lightweight name-match scan of the question
against existing entities). `core/retrieval/candidate_selection.py` also adds entity-anchored
selection (Step 3): turns that mention the same named entities as the new node, taken by
recency up to `k_entity`.

---

### 5. State-Node-Anchored Retrieval (Interaction IDs)

**Was**: State nodes were added directly to `ctx.state`; they never seeded graph expansion.

**Fixed**: `context_assembly.py` now extracts interaction IDs from each relevant state node
(`creation_turn` + `u.turn for u in sn.updates` + `r.turn for r in sn.relations`), adds those
IDs to the entry_points union, and lets them flow into 1-hop graph expansion. Open questions
bypass the similarity gate (always included regardless of cosine score). State node labels are
still injected as `ctx.state` items directly for the state-context section of the prompt (this
is additional, not a replacement).

---

### 6. Epistemic Status Blocking for `superseded`

**Was**: `_propagate_epistemic_status` always overwrote the target's status, allowing `resolves`
to incorrectly clear a `superseded` node to `resolved`.

**Fixed**: `orchestrator.py` now defines `resolve_new_status(current, label)` implementing the
Section 3.5 state-dependent table exactly:

- `revises` → always superseded (regardless of current status)
- `current == superseded` → stays superseded (blocks both resolves and contradicts)
- `resolves` → resolved (clears open or contested)
- `contradicts` → contested

`_propagate_epistemic_status` uses this function and always appends to `epistemic_history`
even when the status did not change, preserving full provenance. The `STATUS_EFFECT` dict was
removed; the logic lives in `resolve_new_status` instead.

---

### 7. Recurrence Count — W2 and All W3 Edges

**Was**: `recurrence_count` was only incremented for W3 epistemic-trigger edges (revises,
contradicts, resolves). W2 edges never incremented it. W3 depends_on and references were skipped.

**Fixed**: `recurrence_count` is now incremented for every stored W2 edge (all hierarchical
edges) AND every stored W3 edge (all pragmatic edges), matching `bump_recurrence(cand_id)` in
the Section 5.7 `apply_w2` / `apply_w3` pseudocode. `_propagate_epistemic_status` no longer
increments it (that was the wrong location).

---

### 8. Retrieval Count (`bump_retrieval`)

**Was**: `retrieval_count` existed in the schema but was never incremented.

**Fixed**: `context_assembly.py` increments `node.retrieval_count` for every node placed in
`ctx.recent` or the historical layers when `profile.count_retrieval` is True. This matches the
Section 5.5 pseudocode's `bump_retrieval(node)` call. The `ANSWER_PROFILE` has
`count_retrieval=True`; `EDGE_PROFILE` has `count_retrieval=False` (write-time candidate
selection is a different event).

---

### 9. EDGE_PROFILE Parameter Values

**Was**: Implementation had `n_recent=0`, `k_semantic=8`, `k_entity=0`, `k_state=0`,
`graph_slots_fraction=0.0`. This made it semantic-only with no graph expansion.

**Fixed**: `EDGE_PROFILE` now matches Section 5.5: `n_recent=1`, `k_semantic=3`, `k_entity=2`,
`k_state=2`, `graph_slots_fraction=0.5`. `ANSWER_PROFILE` also corrected: `k_entity=2`,
`k_state=2` (both were 3 in the old implementation).

---

### 10. Prompt Output Format (W1, W2, W3)

**Was**: W1 used key `"named_entities"` (should be `"entities"`). W2/W3 used list format
`{"edges": [...]}` (should be dict `{"<candidate_id>": "<label>", ...}`).

**Fixed**: All five prompt files and their parsers in `core/pipeline/steps.py` now match
Section 5.6 exactly. W1 uses `"entities"`. W2/W3 parse the top-level dict directly. The
combined prompt's edge keys (`"hierarchical_edges"`, `"pragmatic_edges"`) also match. Each
prompt has a few-shot example taken directly from the Section 4 worked example.

---

### 11. Combined-Call Dispatch Path

**Was**: `PipelineConfig.strategy = "combined_call"` was accepted but ignored; the orchestrator
always ran multi-call.

**Fixed**: `orchestrator.py` now has `_run_combined_extraction()`. When
`settings.pipeline.strategy == "combined_call"`, it: (1) embeds the node, (2) selects candidates,
(3) calls `CombinedExtraction.run()` once with all inputs, (4) applies the combined result
(W1+W2+W3+W4+W5) to the node. `CombinedExtraction` and `CombinedResult` are implemented in
`core/pipeline/steps.py`.

---

### 12. Compression Tier Selection

**Was**: Always FULL for recency/semantic, always SUMMARY for graph. No token-budget logic.

**Status**: Partially addressed. When `profile.compress=True`, graph slots use SUMMARY tier;
when False, they use FULL. State items always use REFERENCE. This matches the practical
behaviour described in the research doc for each layer, though it is a simpler approximation
than the greedy first-fit against a real token budget that the doc describes in Section 3.6.
The live-rendered Tier 3 `render_reference` (building a reference string from state_node_links)
is not yet implemented; the stored W5 `reference` field is used as a fallback. These are
noted below as remaining items.

---

### 13. Wave Architecture (EMBED + W1 + W5 Parallel)

**Was**: W1→candidates→W2→W3→W4→W5 sequential. Per-turn latency = sum of all calls.

**Fixed**: `orchestrator._run_extraction()` now implements the three-wave concurrent design
from Section 5.7 using `concurrent.futures.ThreadPoolExecutor`:

- **Wave 1**: EMBED + W1 + W5 launch immediately (need only raw turn)
- **Wave 2**: W4 starts as soon as EMBED completes
- **Wave 3**: W2 + W3 start once both EMBED and W1 have completed; they run in parallel with each other

Wall-clock cost is now the slowest wave, not the sum. The stale "TWO KNOWN GAPS" comment and
the `AsyncTurnPipeline` stub have been removed from the orchestrator.

---

### 14. Frontend / Backend Schema Consistency

**Was**: `types/api.ts StateNodeStatus` contained stale values `superseded`, `satisfied`,
`violated` from the old schema, and was missing `open`, `reverted`, `lifted`. `graphStyles.ts`
`STATUS_STYLE` had entries for the stale values and was missing the new ones.
`isInactiveState()` incorrectly included `revised` (which is non-terminal) and `superseded`
(which is not a `StateNodeStatus`).

**Fixed**:

- `types/api.ts`: `StateNodeStatus` updated to `'active' | 'open' | 'achieved' | 'abandoned' | 'revised' | 'reverted' | 'lifted' | 'resolved'`
- `graphStyles.ts`: `STATUS_STYLE` updated to cover all 8 status values (4 epistemic + 8 state, with `open` and `resolved` shared). Removed `satisfied` and `violated` entries.
- `graphStyles.ts`: `isInactiveState()` now correctly identifies terminal states: `resolved | abandoned | reverted | lifted | achieved`. Removed `revised` (still active) and `superseded` (not a `StateNodeStatus`).
- `app/backend/dependencies.py`: `get_llm_client()` now selects `OpenAICompatClient` when `GM_OPENAI_BASE_URL` is set, matching the same priority order as `ingest_conversation.py`.

---

## Remaining Known Gaps

These items are documented rather than fixed. All are explicitly noted as "future refinements"
in the research doc or are marked as Phase 4 work.

### R1. Greedy First-Fit Token Budget for Compression

The research doc (Section 3.6) describes `choose_compression_tier` as greedy first-fit against
a remaining token budget. The current implementation chooses tiers per layer type (FULL for
recency/semantic, SUMMARY for graph when compress=True). The practical content is the same —
the tier ordering is correct — but the selection criterion is slot-type rather than
token-count. Implementing real token budgeting requires knowing the model's context window and
estimating token counts per node, which adds coupling to the model layer.

### R2. Live-Rendered Reference Tier (Tier 3)

The research doc's `render_reference` builds a live reference string from a node's
`state_node_links` (creation turn decision → update turn status → entity mention). The current
implementation falls back to the W5-stored `reference` field. This is noted in the research
doc's Section 5.5 as "a starting point" and the live-rendered form as "the next refinement."

### R3. Live Chat Concurrency (Multi-Worker)

`/api/chat/turn` uses a per-conversation in-process lock. This does not survive multiple Uvicorn
workers. The module docstring explains this. Section 6, item 10 of the research doc flags it as
an open design item.

### R4. Compression Weighted by epistemic_status / recurrence_count

The research doc (Section 3.6, footnote) notes compressing superseded nodes harder and
protecting high-recurrence nodes as "next refinements." Not implemented; deferred to Phase 4.

---

## Summary

| #   | Item                                      | Status                                                        |
| --- | ----------------------------------------- | ------------------------------------------------------------- |
| 1   | SLM / multi-provider client               | **Resolved** — `OpenAICompatClient` added                     |
| 2   | State node status schema                  | **Resolved** — all 8 status values per Section 3.3.1          |
| 3   | `r_pragmatic` + 5 comparison profiles     | **Resolved** — all profiles in `config.py`                    |
| 4   | Entity-anchored retrieval                 | **Resolved** — context assembly + candidate selection         |
| 5   | Epistemic status blocking (`superseded`)  | **Resolved** — `resolve_new_status()`                         |
| 6   | State-node retrieval → interaction IDs    | **Resolved** — entry points from sn.creation_turn etc.        |
| 7   | Recurrence count (W2 + all W3 edges)      | **Resolved** — incremented in W2/W3 application               |
| 8   | Retrieval count (`bump_retrieval`)        | **Resolved** — incremented in `context_assembly.py`           |
| 9   | EDGE_PROFILE + ANSWER_PROFILE values      | **Resolved** — match Section 5.5                              |
| 10  | W1/W2/W3 prompt output format             | **Resolved** — match Section 5.6 dict format                  |
| 11  | Combined-call dispatch path               | **Resolved** — `_run_combined_extraction()`                   |
| 12  | Compression tier selection                | **Partially resolved** — tier per layer; token budget not yet |
| 13  | Wave architecture                         | **Resolved** — ThreadPoolExecutor three-wave concurrency      |
| 14  | Frontend/backend schema consistency       | **Resolved** — `StateNodeStatus`, `isInactiveState`           |
| R1  | Greedy first-fit token budget             | Remaining — Phase 4 refinement                                |
| R2  | Live-rendered Tier 3 reference            | Remaining — Phase 4 refinement                                |
| R3  | Live chat multi-worker concurrency        | Remaining — design open item                                  |
| R4  | Compression weighted by status/recurrence | Remaining — Phase 4 refinement                                |
