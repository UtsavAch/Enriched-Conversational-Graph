# Consistency Report: Implementation vs. INESCTEC_RESEARCH.md

---

## 1. No SLM / Multi-Provider Support — Critical for Evaluation Plan

**Research intent**: Use Claude for development but swap in SLMs for evaluation comparisons.

**Implementation**: `client.py` defines `LLMClient` as a narrow `Protocol` with a single `complete(system, user, ...) -> LLMResponse` method — this is well-designed for swapping. However, only `AnthropicClient` and `StubLLMClient` are implemented. `ModelConfig` defaults are Anthropic model IDs. There is no `OllamaClient`, `OpenAICompatClient`, or any other provider implementation.

**What needs to be done**: Add at minimum an OpenAI-compatible client (Ollama exposes this API), so any local SLM can be plugged in by just pointing to `http://localhost:11434/v1`. The `Protocol` is already the right abstraction — it just needs a second implementation.

---

## 2. State Node Status Schema — Significant Divergence

The status values in the implementation differ from the research doc in ways that matter for the W4 prompt, the evaluation, and inter-system comparisons.

| Type | Research doc (Section 3.3.1) | Implementation (`enums.py` / W4 prompt) |
|---|---|---|
| `goal` | active, achieved, abandoned | active, achieved, abandoned, **revised** (added) |
| `decision` | active, revised, **reverted** | active, revised, **superseded** (renamed) |
| `constraint` | active, **lifted**, revised | active, **satisfied, violated**, revised |
| `open_question` | **open**, resolved | **active**, resolved, abandoned (added) |

Specific problems:

- `decision.reverted` (research) → `decision.SUPERSEDED` (impl). Different word, different meaning: "reverted" = undone entirely; "superseded" = overridden by something newer. These are not synonyms.
- `constraint.lifted` (research) → gone entirely. The impl uses `SATISFIED` and `VIOLATED` instead, which are categorically different semantics (outcome of checking the constraint vs. removing it).
- `open_question` starts as `open` in the research doc; the impl uses `ACTIVE` for all state nodes including open questions. The `bypass_similarity_gate_for = "open_question"` heuristic in the retrieval pseudocode relies on open_question nodes being distinguishable by their status ("open"), which collapses if everything is ACTIVE.
- The W4 prompt file (`w4_state_nodes.txt`) has already been updated to match the implementation's status values (`decision → superseded`, `constraint → satisfied/violated`). So the prompt and the parser are internally consistent — but both diverge from the research document.

**This is the most significant schema divergence.** If you plan to evaluate against the research doc's worked example or gold annotations, the status labels will not match.

---

## 3. Comparison Profiles (Task 4.4) — Not Implemented

The research doc (Section 5.5) defines five named profiles for the ablation study required for Phase 4:

| Profile | Parameters |
|---|---|
| `RECENCY_ONLY_PROFILE` | N_recent=45 (forces K_historical=0) |
| `BASELINE_SEMANTIC_PROFILE` | f_graph=0.0, K_entity=0, K_state=0 |
| `BASELINE_HIERARCHICAL_PROFILE` | r_pragmatic=0.0, K_entity=0, K_state=0 |
| `PRAGMATIC_ONLY_PROFILE` | r_pragmatic=1.0, K_entity=0, K_state=0 |
| `ENRICHED_PROFILE` | = ANSWER_PROFILE (r_pragmatic=NULL) |

None of these are defined anywhere in the codebase. More critically, `ContextProfile` has no `r_pragmatic` field at all, so `BASELINE_HIERARCHICAL_PROFILE` and `PRAGMATIC_ONLY_PROFILE` cannot be expressed. The `context_assembly.py` `assemble()` method has `use_graph: bool` and `use_documents: bool` ablation flags, which can reproduce some baselines but not the hierarchical/pragmatic pool split.

**What needs to be added**:

1. `r_pragmatic: float | None` field on `ContextProfile`
2. The five named profile constants in `config.py`
3. The split-pool scoring logic in `context_assembly.py` — step 4 of the pseudocode tracks `scored_hierarchical` and `scored_pragmatic` as separate dicts, then allocates graph slots proportionally when `r_pragmatic` is not NULL
4. A way to pass the profile to `run_validation.py` as a CLI argument for the sweep

---

## 4. Entity-Anchored Retrieval — Defined but Never Used

`k_entity` exists on `ContextProfile` (`k_entity=3` in `ANSWER_PROFILE`), but `context_assembly.py` never touches it. The entity-anchored entry point generation in the pseudocode (Section 5.5, Step 2) is:

```
entity_entries = top_k_by_recency(
    entity_registry[eid].mentioned_in  for eid in seed_entities
)
```

This is entirely absent from `ContextAssembler.assemble()`. The graph expansion currently uses only semantic entry points (`seeds` dict). Entity mentions cannot seed graph expansion, and the `k_entity` slot in the profile is unused dead weight.

The same applies in `candidate_selection.py` (`select_edge_candidates`): the EDGE_PROFILE has `k_entity=2` in the research doc and `k_entity=0` in the implementation, and the function never does entity-anchored selection regardless.

---

## 5. State-Node-Anchored Retrieval — Partially Wrong

The research pseudocode converts state nodes into **interaction node entry points**:

```
state_entries = flatten(
    [sn.creation_turn] + [pair[0] for pair in sn.last_updated_turn.updates]
                       + [pair[0] for pair in sn.last_updated_turn.relates]
    for sn in state_matches
) MINUS excluded
```

These interaction IDs then enter the entry_points union and get 1-hop expanded via the graph.

The implementation (`context_assembly.py`) instead adds state nodes directly to `ctx.state` as semantic-similarity matches and renders them inline in the prompt. State nodes never seed graph expansion. This is a different mechanism: the research design uses state nodes as *indirect pointers to relevant interactions*, while the implementation injects the state node labels themselves.

Also missing: the `bypass_similarity_gate_for = "open_question"` logic that forces open questions into the candidate set even when their embedding is distant from the current query.

---

## 6. Epistemic Status Propagation — Missing Blocking Logic

The research doc (Section 3.5) defines a state-dependent transition table where `superseded` is effectively terminal for incoming `resolves` and `contradicts`:

```
current=superseded + resolves arrives   → BLOCKED (stays superseded)
current=superseded + contradicts arrives → BLOCKED (stays superseded)
current=superseded + revises arrives    → superseded (no-op, "still wins")
```

The implementation (`_propagate_epistemic_status`):

```python
STATUS_EFFECT = {REVISES: SUPERSEDED, CONTRADICTS: CONTESTED, RESOLVES: RESOLVED}

for edge in node.pragmatic_edges:
    effect = STATUS_EFFECT.get(edge.relation)
    ...
    target.epistemic_status = effect   # always overwrites, no blocking check
```

A `resolves` edge arriving at a `superseded` node will incorrectly set it to `resolved`. The research doc is explicit that `superseded` blocks both `resolves` and `contradicts`. The `resolve_new_status` pseudocode in Section 5.7 handles this correctly (checks `current == "superseded"` before applying the label effect), but that logic was not translated into the implementation.

Also: the research doc says blocked edges should still be appended to `epistemic_history` for provenance even when they don't change the status. The implementation doesn't log them at all.

---

## 7. Recurrence Count — Only Partially Incremented

The research pseudocode (`apply_w2` and `apply_w3`, Section 5.7) calls `bump_recurrence(cand_id)` for every stored edge, both hierarchical and pragmatic.

The implementation only increments `target.recurrence_count` inside `_propagate_epistemic_status`, which only fires for `REVISES`, `CONTRADICTS`, and `RESOLVES` (the three epistemic-trigger relations). Two gaps:

- **W2 hierarchical edges**: never increment `recurrence_count`
- **W3 `depends_on` and `references` edges**: never increment `recurrence_count`

---

## 8. Retrieval Count — Never Incremented

`InteractionNode.retrieval_count` exists in the schema but `context_assembly.py` never calls anything like `bump_retrieval`. This means the metric is always 0. The research doc uses it for diagnostics (visibility of long-tail nodes, whether high-recurrence nodes are actually getting retrieved). It is noted as having a `count_retrieval` flag in the profile (`true` for `ANSWER_PROFILE`, `false` for `EDGE_PROFILE`), but neither the flag nor the increment exist in the implementation.

---

## 9. EDGE_PROFILE Parameter Values Differ

| Parameter | Research doc (Section 5.5) | Implementation (`config.py`) |
|---|---|---|
| `n_recent` | 1 | 0 |
| `k_semantic` | 3 | 8 |
| `k_entity` | 2 | 0 |
| `k_state` | 2 | 0 |
| `f_graph (graph_slots_fraction)` | 0.5 | 0.0 |

The implementation's EDGE_PROFILE is effectively "semantic-only with no graph expansion and no entity/state anchoring." The research doc's EDGE_PROFILE includes entity and state anchoring and 50% graph slots, reflecting the design intent that write-time candidates should benefit from the same multi-source retrieval as answer-time candidates, just under a smaller budget.

`ANSWER_PROFILE` also has minor differences: `k_entity=2` (doc) vs `3` (impl), `k_state=2` (doc) vs `3` (impl).

---

## 10. Prompt Output Format Differences (W1, W2, W3 vs. Research Doc)

These are internally consistent (prompt and parser agree) but diverge from the research doc specification.

**W1**: Research doc specifies key `"entities"`. Prompt (`w1_extraction.txt`) and parser both use `"named_entities"`. Minor but diverges from the spec's worked example output.

**W2/W3**: Research doc specifies dict format `{"<candidate_id>": "<label>", ...}`. Both prompt files and parser use list format `{"edges": [{"target": "...", "relation": "..."}, ...]}`. The list format is arguably more robust (easier to add fields), but anyone comparing against the research doc's few-shot examples will see a different JSON shape.

---

## 11. Combined-Call Strategy — Prompt Written, Code Path Missing

`PipelineConfig.strategy` accepts `"combined_call"` and `combined_extraction.txt` exists (with the full combined prompt from Section 5.6). But `orchestrator._run_extraction()` always runs multi_call (W1–W5 sequentially) regardless of `strategy`. There is no combined-call dispatch path. The comparison the research doc says "should be a configuration change, not a rewrite" currently requires writing the dispatch code.

---

## 12. Compression Tier Selection — Simplified

The research doc (Sections 3.6, 5.5) specifies:

- `choose_compression_tier`: greedy first-fit against a **token** budget
- `render_reference`: live-rendered from state node label + status, with priority order (creates → updates → entity mentions → W5 stored reference)
- `count_retrieval` flag in the profile

The implementation hard-codes:

- Recency items → always FULL
- Semantic items → always FULL
- Graph items → always SUMMARY
- State items → always REFERENCE (inline label)

There is no token-budget-based tier selection. `render_reference` (the live-rendered Tier 3 text) is not implemented. `node.reference` (the W5-stored fallback) exists but is only used by the `render` method on the node itself. The important consequence: a graph-slot node with a linked state decision always shows its `summary` field, not the live-rendered `[decision] Adopt five pragmatic edge types` pointer that the research doc describes.

---

## 13. Wave Architecture — Acknowledged Gap

The research doc (Section 5.7) defines three waves with specific dependency ordering (EMBED+W1+W5 in Wave 1, W4 in Wave 2, W2+W3 in Wave 3). The implementation runs W1→candidates→W2→W3→W4→W5 sequentially. W5 runs last, not in Wave 1, meaning per-turn latency is the sum of all calls rather than the max of the slowest wave. This is acknowledged in the orchestrator docstring and at the bottom of the file (`AsyncTurnPipeline` stub). Do not report Phase 2 latency estimates as met by the current code.

---

## Summary Table

| # | Item | Severity | Status |
|---|---|---|---|
| 1 | No SLM / multi-provider client | Critical (blocks evaluation plan) | Missing |
| 2 | State node status names differ from research doc | High (schema divergence, eval mismatch) | Diverged |
| 3 | `r_pragmatic` + 5 comparison profiles | High (blocks Task 4.4) | Missing |
| 4 | Entity-anchored retrieval (`k_entity` unused) | High (design intent not implemented) | Missing |
| 5 | Epistemic status blocking for `superseded` | Medium (incorrect graph writes possible) | Missing |
| 6 | State-node retrieval → interaction entry points | Medium (wrong mechanism) | Diverged |
| 7 | Recurrence count (W2 + `depends_on`/`references`) | Medium (metric incorrect) | Partial |
| 8 | Retrieval count (`bump_retrieval`) | Medium (metric always 0) | Missing |
| 9 | EDGE_PROFILE values differ from doc | Medium (affects edge candidate quality) | Diverged |
| 10 | Combined-call dispatch path | Medium (research comparison blocked) | Missing |
| 11 | Compression tier selection (token budget) | Low–Medium (retrieval cost higher than design) | Simplified |
| 12 | W1/W2/W3 prompt JSON format vs. doc | Low (internally consistent, diverges from spec) | Diverged from spec |
| 13 | ANSWER_PROFILE `k_entity`/`k_state` off by 1 | Low | Diverged |
| 14 | Wave concurrency (EMBED+W1+W5 parallel) | Known deferred | Acknowledged in code |
