# Prompt v4 vs v3: extraction evaluation (2026-09-27)

## Summary

Prompt version v4 (see `core/llm/prompts/CHANGELOG.md`) was evaluated against the previous
version v3 by re-ingesting two corpora with gemma4:31b and scoring both graphs against the same
gold annotation.

- **Entities improved strongly on both corpora**: F1 +0.120 (`hpc_support`) and +0.243
  (`rest_api`), with precision *and* recall both up. The unique entity count fell from 100 to 62
  and from 115 to 51.
- **Relations improved overall**: macro F1 +0.079 and +0.071, with both the hierarchical and the
  pragmatic families up on both corpora. `supercase` (+0.22, +0.17), `revises` (+0.50 on
  `hpc_support`) and `contradicts` (0 → 0.50 on `rest_api`) gained most.
- **`references` got worse on `rest_api`** (0.324 → 0.203). The cause is mostly not the prompt: most
  cited turns are never shown to the classifier as candidates (see Diagnosis). **Fixed in the
  follow-up**: with cited turns always offered as candidates, `references` F1 rises to 0.536 on
  turns 1-40 (v4 alone: 0.255), at the cost of a lower `same_level` F1 (0.421 → 0.286).
- **State-node over-creation halved on `hpc_support`** (38 → 19, gold 13), but barely changed on
  `rest_api` (83 → 77, gold 56), and v4 created **no constraints** there (gold 7). State-node match
  counts can't be interpreted yet because the matcher only credits near-verbatim labels.

This is **one run per corpus** on the two corpora the revision was designed from, so it measures
fit on the development data, not generalisation. The six untouched testbeds are the held-out check.

## Setup

| | |
|---|---|
| Model | gemma4:31b on the institute Ollama server, reasoning off (`reasoning_effort="none"`) |
| Strategy | `multi_call` (W1-W5), profile `enriched`, `hashing` embedder |
| Prompts | v3 = `versions/v3` (2026-09-17) · v4 = `versions/v4` (2026-09-27) |
| Graphs | v3: `rest_api_gemma4`, `hpc_support_gemma4` (2026-09-26) · v4: `rest_api_gemma4_p2`, `hpc_support_gemma4_p2` (2026-09-27) · v4 + cited candidates: `rest_api_gemma4_p3` (2026-09-27, turns 1-40 only) |
| Gold | `data/eval_corpora/{rest_api,hpc_support}.json` |
| Metrics | commit `fe2ce61`: relations scored per family (hierarchical and pragmatic), entity match = normalised name per turn, state nodes = token Jaccard ≥ 0.4 |
| Extraction errors | 0 per-turn errors in all four runs; 248 model calls per corpus (5.0 per turn) |

## Results

### `hpc_support` (50 turns)

| Metric | v3 | v4 | Change |
|---|---|---|---|
| Unique entities | 100 | 62 | −38 |
| Entity precision | 0.247 | 0.362 | +0.114 |
| Entity recall | 0.677 | 0.723 | +0.046 |
| **Entity F1** | 0.362 | **0.482** | **+0.120** |
| Relations predicted (gold 99) | 142 | 106 | −36 |
| **Relation macro F1** | 0.288 | **0.367** | **+0.079** |
| Hierarchical macro F1 | 0.366 | 0.447 | +0.081 |
| Pragmatic macro F1 | 0.241 | 0.319 | +0.078 |
| subcase F1 | 0.655 | 0.674 | +0.019 |
| supercase F1 | 0.444 | 0.667 | +0.222 |
| same_level F1 | 0.000 | 0.000 | 0 |
| depends_on F1 | 0.538 | 0.500 | −0.038 |
| references F1 | 0.000 | 0.000 | 0 |
| resolves F1 | 0.667 | 0.593 | −0.074 |
| revises F1 | 0.000 | 0.500 | +0.500 |
| contradicts F1 | 0.000 | 0.000 | 0 |
| State nodes predicted (gold 13) | 38 | 19 | −19 |
| State nodes by type | goal 6, constraint 9, decision 16, open_question 7 | goal 1, constraint 4, decision 9, open_question 5 | |

### `rest_api` (50 turns)

| Metric | v3 | v4 | Change |
|---|---|---|---|
| Unique entities | 115 | 51 | −64 |
| Entity precision | 0.368 | 0.614 | +0.246 |
| Entity recall | 0.654 | 0.853 | +0.199 |
| **Entity F1** | 0.471 | **0.714** | **+0.243** |
| Relations predicted (gold 171) | 188 | 144 | −44 |
| **Relation macro F1** | 0.342 | **0.412** | **+0.071** |
| Hierarchical macro F1 | 0.350 | 0.405 | +0.055 |
| Pragmatic macro F1 | 0.337 | 0.417 | +0.080 |
| subcase F1 | 0.585 | 0.592 | +0.006 |
| supercase F1 | 0.148 | 0.316 | +0.168 |
| same_level F1 | 0.316 | 0.308 | −0.008 |
| depends_on F1 | 0.493 | 0.494 | +0.001 |
| references F1 | 0.324 | 0.203 | −0.120 |
| resolves F1 | 0.533 | 0.600 | +0.067 |
| revises F1 | 0.333 | 0.286 | −0.048 |
| contradicts F1 | 0.000 | 0.500 | +0.500 |
| State nodes predicted (gold 56) | 83 | 77 | −6 |
| State nodes by type | goal 2, constraint 5, decision 69, open_question 7 | goal 1, constraint 0, decision 67, open_question 9 | |

Note on `rest_api`: v3's W1 prompt contained a few-shot example copied from this corpus
(Article/Source), which v4 removed. v4 still scores far higher, so the entity gain is not an
artefact of that leak.

## Diagnosis

**Entities.** The v3 false positives were mostly names that never appear in the gold at all: field
names, HTTP verbs, commands with their arguments, file paths, generic words. v4's canonical-name
rules and do-not-extract list remove most of them, and the canonical singular form also raises
recall: on `rest_api`, v3 split `Article`/`articles` and `Topic`/`topics` into separate entities,
while v4 uses only the canonical names and finds them in more turns (`User` 3 → 5 turns, `Article`
18 → 24, `Topic` 12 → 14). Some listed items still get through
(`cpu`, `environment.yml` on `hpc_support`), so the rules are followed well but not perfectly.

**Hierarchical relations.** The immediate-parent rule reduced over-linking (predicted relations
−36 and −44), and supercase precision rose. `subcase` barely moved (+0.006 / +0.019) because it
was already the best-scoring label, and `same_level` stays weak on both corpora.

**`references` and citations.** v4 says a cited candidate is never `no_relation`. Of the 74
`[N_k]` citations in `rest_api` answers, 28 (v3) and 27 (v4) pairs still end up with no pragmatic
label. The reason is candidate selection, not the prompt: W2/W3 only see the 2 most recent turns,
1 semantically similar turn and 2 entity-sharing turns
(`core/retrieval/candidate_selection.py`), and a cited turn is not guaranteed to be among them,
especially with the `hashing` embedder. Where cited turns *are* candidates, the rule "use the most
specific label" moved 6 gold `references` to `depends_on`. So v4 raises coverage of what the
classifier sees but cannot reach citations it isn't shown.

**State nodes.** v4's stricter definitions halved over-creation on `hpc_support` (goals 6 → 1:
single requests are no longer goals), but on `rest_api` almost every turn in the design dialogue
is a genuine decision, so the count barely changed (69 → 67 decisions). The constraint definition
now looks too strict: v4 created no constraints on `rest_api`, where the gold has 7. The
"matched" count (1 → 1, 1 → 0) is not informative: the metric requires token Jaccard ≥ 0.4
between labels, so paraphrases of the same commitment don't match.

## Follow-up: cited turns as W2/W3 candidates (turns 1-40)

Following the diagnosis above, `select_edge_candidates` now always adds the prior turns an answer
cites as `[N_k]` (up to 5 per turn) on top of the recency, semantic and entity candidates
(commit `1313492`, `tests/test_candidate_selection.py`).

**Offline replay** of candidate selection on the stored v4 graphs (no model calls):

| | Gold pragmatic pairs shown to W3 | Gold hierarchical pairs shown to W2 | Candidates per turn |
|---|---|---|---|
| `rest_api`, v4 | 62/90 (69%) | 55/81 (68%) | 4.46 |
| `rest_api`, v4 + cited | **89/90 (99%)** | **71/81 (88%)** | 5.00 |
| `hpc_support`, v4 | 42/50 (84%) | 41/49 (84%) | 3.90 |
| `hpc_support`, v4 + cited | 44/50 (88%) | 42/49 (86%) | 3.96 |

**Re-ingest of `rest_api` with v4 + cited candidates** (`rest_api_gemma4_p3`). The shared Ollama
server stopped generating during turn 41 and the run was stopped there with 40 clean turns, so all
three runs are compared on **turns 1-40** (gold: 125 entity mentions, 134 relations, 58 cited
pairs):

| Metric | v3 | v4 | v4 + cited | v4 → v4 + cited | Gold edges (1-40) |
|---|---|---|---|---|---|
| Entity F1 | 0.488 | 0.737 | 0.737 | 0 | |
| Relation macro F1 | 0.375 | 0.474 | 0.480 | +0.006 | 134 |
| Hierarchical F1 | 0.380 | 0.476 | 0.441 | −0.036 | 65 |
| Pragmatic F1 | 0.373 | 0.473 | **0.503** | **+0.031** | 69 |
| references F1 | 0.393 | 0.255 | **0.536** | **+0.280** | 26 |
| depends_on F1 | 0.571 | 0.551 | 0.548 | −0.003 | 35 |
| resolves F1 | 0.500 | 0.750 | 0.500 | −0.250 | 3 |
| revises F1 | 0.400 | 0.308 | 0.267 | −0.041 | 4 |
| contradicts F1 | 0.000 | 0.500 | 0.667 | +0.167 | 1 |
| subcase F1 | 0.634 | 0.692 | 0.683 | −0.009 | 44 |
| supercase F1 | 0.148 | 0.316 | 0.353 | +0.037 | 8 |
| same_level F1 | 0.357 | 0.421 | 0.286 | −0.135 | 13 |
| Cited pairs given a pragmatic label | 41/58 | 42/58 | **58/58** | | |
| State nodes created (gold 44) | 68 | 63 | 63 | 0 | |

- **The targeted problem is fixed.** Every cited pair now reaches W3 and gets a pragmatic label
  (58/58), and `references` F1 more than doubles (0.255 → 0.536), recovering the v4 regression and
  ending above v3.
- **The cost is a modest drop in `same_level`** (0.421 → 0.286 on 13 gold edges): with more, and
  older, candidates on the table, the model marks a few of them as parallel topics. Hierarchical
  F1 falls 0.036 as a result. The `resolves`, `revises` and `contradicts` changes are one edge
  each (3, 4 and 1 gold edges) and are within noise.
- **Runs are repeatable.** The candidate change does not touch W1 or W4, and entity scores and
  state-node counts are identical between the v4 and v4 + cited runs. At temperature 0, gemma4's
  extraction repeats exactly, so the relation differences come from the change itself.

## Recommended next steps

1. ~~Always include cited turns as W2/W3 candidates.~~ Done (see follow-up above). If `same_level`
   matters for the thesis, a variant that adds cited turns to W3's candidates only (W2 keeps the
   old set) should keep the `references` gain without the `same_level` cost.
2. **Loosen the W4 constraint definition slightly**, so limits the user states for this project
   (e.g. an API design rule the team adopts) still count, then re-check `rest_api` constraints.
3. **Replace or supplement the state-node matcher** (e.g. an embedding or LLM-judged match) before
   reading state-node precision/recall as a quality signal.
4. **Confirm on held-out data**: ingest the six new testbeds with v3 and v4 (about 20 minutes per
   corpus per version) to check the gains generalise beyond the two corpora v4 was designed from.
5. **Treat small labels with care**: runs repeat exactly at temperature 0 (see follow-up), so the
   remaining uncertainty is not run-to-run noise but tiny gold support: `contradicts` has 1-2
   gold edges per corpus, `resolves` and `revises` 3-5. The held-out testbeds (22 `contradicts`,
   27 `revises` in total) are where those labels can be measured.

## Reproduction

```
# v3 graphs: rest_api_gemma4, hpc_support_gemma4 (built 2026-09-26 with the prompts now in versions/v3)
# v4 graphs:
python -m scripts.ingest_conversation ../conversations/hpc_support/corpus.json \
    --conversation-id hpc_support_gemma4_p2 --profile enriched \
    --domain-config ../conversations/hpc_support/domain_config.json
python -m scripts.ingest_conversation ../conversations/rest_api/corpus.json \
    --conversation-id rest_api_gemma4_p2 --profile enriched \
    --domain-config ../conversations/rest_api/domain_config.json
# with GM_OPENAI_BASE_URL / GM_EXTRACTION_MODEL=gemma4:31b / GM_REASONING_EFFORT=none;
# add GM_PROMPT_VERSION=v3 to rebuild with the old prompts.
```

Scores come from `evaluation.metrics` (`entity_prf`, `per_relation_prf`, `evaluate_state_nodes`)
applied to `extract_predictions(graph)` against the gold files above.
