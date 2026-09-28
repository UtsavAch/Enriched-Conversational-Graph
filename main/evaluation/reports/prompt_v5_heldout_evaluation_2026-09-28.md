# Prompt v5 vs v3 on held-out testbeds (2026-09-28)

## Summary

The prompt revisions v4 and v5 were designed from errors on two development corpora (`rest_api`,
`hpc_support`; see `prompt_v4_evaluation_2026-09-27.md`). This evaluation checks whether the gains
carry over to six testbeds that played **no part** in designing them.

**v5 is better than v3 on the held-out data on every aggregate measure**, pooled over six corpora
(716 gold relations, 79 gold state nodes):

- **Entity F1 +0.049** (0.399 → 0.448), with precision and recall both up.
- **Relation macro F1 +0.032** (0.283 → 0.315): hierarchical +0.044, pragmatic +0.026.
- **Largest label gains**: `supercase` +0.102 and `contradicts` +0.088. No relation label gets
  worse; `depends_on` and `same_level` are unchanged.
- **Less over-creation**: 27% fewer state nodes (222 → 162, gold 79), and 11 goals instead of 26
  (gold 9).

The gains are real but **about a third to a half of those measured on the development corpora**
(entity F1 there +0.12 and +0.24, relations +0.07 and +0.08), which is the expected gap between
the data a revision was designed on and new data.

## Setup

| | |
|---|---|
| Prompts | v3 = `core/llm/prompts/versions/v3` (2026-09-17) · v5 = `versions/v5` (2026-09-27) |
| Code | `main` at `258b294` for both versions, so both use the same pipeline, including cited-turn candidates; only `GM_PROMPT_VERSION` differs |
| Model | gemma4:31b on the institute Ollama server, thinking off (`GM_REASONING_EFFORT=none`), `multi_call`, profile `enriched`, `hashing` embedder |
| Corpora | `kitchen_reno`, `ml_debugging`, `product_rename`, `tutoring_stats` (50 turns each), `thesis_planning`, `relocation` (80 turns each): 360 turns per version |
| Graphs | `<corpus>_gemma4_v3`, `<corpus>_gemma4_v5` in `data/conversations/` |
| Gold | `data/eval_corpora/<corpus>.json` |
| Metrics | fixed relation metric (hierarchical and pragmatic scored per family); entity match = normalised name per turn |
| Pooling | predictions and gold of all corpora combined (turn ids prefixed by corpus), so labels with small per-corpus support are scored on all their held-out edges |
| Run integrity | 12 runs, 0 per-turn errors, 0 failed extraction steps. The server dropped out 11 times; the runner paused each affected call and retried it once the server generated again, so no turn was saved half-extracted |

## Pooled results (6 held-out corpora)

| Metric | v3 | v5 | Change | Gold |
|---|---|---|---|---|
| Entity precision | 0.346 | 0.393 | +0.048 | |
| Entity recall | 0.471 | 0.519 | +0.048 | |
| **Entity F1** | 0.399 | **0.448** | **+0.049** | |
| Relations predicted | 1241 | 968 | −273 | 716 |
| **Relation macro F1** | 0.283 | **0.315** | **+0.032** | |
| Hierarchical F1 | 0.333 | 0.377 | +0.044 | 362 |
| Pragmatic F1 | 0.253 | 0.278 | +0.026 | 354 |
| subcase F1 | 0.466 | 0.492 | +0.026 | 273 |
| supercase F1 | 0.432 | 0.534 | +0.102 | 54 |
| same_level F1 | 0.101 | 0.105 | +0.004 | 35 |
| depends_on F1 | 0.372 | 0.372 | 0.000 | 201 |
| references F1 | 0.064 | 0.080 | +0.015 | 44 |
| resolves F1 | 0.364 | 0.376 | +0.012 | 63 |
| revises F1 | 0.197 | 0.209 | +0.012 | 26 |
| contradicts F1 | 0.267 | 0.355 | +0.088 | 20 |
| State nodes created | 222 | 162 | −60 | 79 |
| goals | 26 | 11 | −15 | 9 |
| decisions | 117 | 82 | −35 | 42 |
| constraints | 30 | 35 | +5 | 12 |
| open questions | 49 | 34 | −15 | 16 |

## Per corpus

| Corpus | Entity F1 v3 → v5 | Relation macro F1 v3 → v5 | State nodes v3 → v5 (gold) |
|---|---|---|---|
| `kitchen_reno` | 0.405 → 0.443 (+0.038) | 0.310 → 0.353 (+0.043) | 40 → 27 (13) |
| `ml_debugging` | 0.359 → 0.356 (−0.002) | 0.310 → 0.323 (+0.013) | 28 → 21 (12) |
| `product_rename` | 0.465 → 0.453 (−0.012) | 0.317 → 0.380 (+0.063) | 37 → 31 (12) |
| `tutoring_stats` | 0.256 → 0.441 (+0.184) | 0.275 → 0.271 (−0.004) | 20 → 13 (12) |
| `thesis_planning` | 0.307 → 0.345 (+0.038) | 0.206 → 0.299 (+0.093) | 49 → 31 (14) |
| `relocation` | 0.542 → 0.573 (+0.031) | 0.292 → 0.296 (+0.004) | 48 → 39 (16) |

Relation macro F1 improves on 5 of 6 corpora and state-node over-creation falls on all 6. Entity
F1 improves on 4 of 6. Its effect depends on the corpus: `tutoring_stats`, whose entities are named
concepts ("p-value", "Kruskal-Wallis test"), gains +0.184 from the canonical-name rules, while the
everyday-domain corpora change little, because they lack the command, path and field-name noise
the entity rules target.

## Findings

**Hierarchical relations: the most robust gain.** The "immediate parent only" rule and the
stricter supercase definition improve hierarchical F1 on 5 of 6 corpora and remove 22% of
predicted relations overall. `supercase` gains most (+0.102).

**`contradicts`: a real gain.** The new definition (refutation by evidence and dropping a decision
count as contradicts) and its example raise F1 from 0.267 to 0.355 over 20 gold edges.

**`references` is still unsolved.** Pooled F1 is 0.064 → 0.080. Only 6 of the first 24 held-out
gold `references` edges examined are `[N_k]` citations; the rest are uncited callbacks ("as we
agreed in May"). Both versions mostly predict `references` on pairs that have no gold relation
(v3: 75 of 90 predictions on the first four corpora; v5: 53 of 59), and v5 tends to label gold
callbacks as `depends_on`. Where citations are frequent (`thesis_planning`), v5's citation rule
helps (0.098 → 0.233).

**State nodes.** v5 creates 27% fewer, with goals close to gold (11 vs 9) and slightly more
constraints (35 vs 30, gold 12), as intended by the v5 constraint definition. It still
over-creates decisions (82 vs 42) and open questions (34 vs 16). State-node *matching* is not
reported: the token-overlap matcher does not credit paraphrased labels (see the v4 report).

## Recommended next steps

1. **Uncited `references`**: add a W3 example of an uncited callback ("as we decided last week,
   ..."), and state that pointing back without building on the earlier turn is `references`, not
   `depends_on`.
2. **Decision over-creation**: add a W4 example of a turn that refines details of an existing
   decision (an update, not a new decision). Decisions are still twice the gold count.
3. **State-node matcher**: replace token overlap with an embedding or LLM-judged match, so
   state-node precision and recall can be reported.
4. **Probe evaluation**: with the graphs now built for all eight corpora, run the consistency
   probes (66 held-out probes) at a small context budget (`k_historical` 5-10), asked
   mid-conversation rather than after the closing recap turns (see the probe findings of
   2026-09-27).

## Reproduction

```
# from main/, with .env pointing at the Ollama server (OLLAMA_BASE_URL, OLLAMA_MODEL=gemma4:31b,
# GM_REASONING_EFFORT=none):
GM_PROMPT_VERSION=v3 python -m scripts.ingest_conversation ../conversations/<corpus>/corpus.json \
    --conversation-id <corpus>_gemma4_v3 --profile enriched \
    --domain-config ../conversations/<corpus>/domain_config.json
GM_PROMPT_VERSION=v5 python -m scripts.ingest_conversation ... --conversation-id <corpus>_gemma4_v5 ...
```

Scores come from `evaluation.metrics` (`entity_prf`, `per_relation_prf`) applied to
`extract_predictions(graph)` against `data/eval_corpora/<corpus>.json`, per corpus and pooled.
