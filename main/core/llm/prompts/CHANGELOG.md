# Prompt changelog

All versions are stored in [`versions/`](versions/README.md) and selectable with
`GM_PROMPT_VERSION=v1|v2|v3|v4`.

## v4 (2026-09-27): revision based on gemma4 error analysis

The previous prompts are v3 (`versions/v3/`). Evidence below comes from gemma4:31b
extraction on `rest_api` and `hpc_support`, scored with the fixed relation metric.

| Prompt | Observed failure | Change |
|---|---|---|
| W1 | Entity precision 0.37 / 0.25; 118 of 153 and 114 of 134 false positives are names that never occur in the gold at all: field names (`source_id`, `MaxRSS`), HTTP verbs and routes with verbs (`POST /me/conversations/...`), commands with arguments (`module load python/3.11`, `--mem=32G`), generic words (`API`, `CPU`, `GPU`). False negatives are canonical names written differently (`users` vs `User`). | Canonical-form rules (bare names, singular concepts, routes without verbs) and an explicit "do not extract" list. |
| W1, W2 | Few-shot examples were copied from the `rest_api` corpus (Article/Source; the `/jobs` generalisation), leaking gold answers into that corpus's evaluation. | Replaced with examples from domains used by no testbed (community garden, podcast). |
| W2 | Subcase edges to the parent's ancestors: 19 of 31 (`rest_api`) and 15 of 33 (`hpc_support`) false subcase edges point to a gold ancestor; 23 and 20 turns get more than one subcase edge (gold: 9 and 0). 15 false supercase on `rest_api`. | "Link to the immediate parent only" rule with a worked example; supercase requires an actual generalising move. |
| W3 | `references` recall 11/36 on `rest_api`. 35 of 36 gold `references` edges come from answers that cite the target as `[N_k]`, and across all 8 gold corpora a cited pair is never `no_relation`, but the old prompt told the model to judge "as if the bracket were not there". | A cited candidate is never `no_relation`: most specific label that fits, otherwise `references`. |
| W3 | `contradicts` recall 0 (predicted as `revises`); `revises` over-predicted (14 vs 4 gold), mostly on gold `depends_on`. The old prompt had no example of either. | Sharper definitions (revises = position now out of date; contradicts includes refutation by evidence and dropping a decision), plus examples for both. |
| W4 | Over-creation: 38 predicted vs 13 gold (`hpc_support`), 83 vs 56 (`rest_api`): goals for single requests, constraints for documentation facts, open questions answered in the same turn. | Stricter definition of each type, "most turns create none" examples, value changes are revisions of the existing node, specific labels naming the key value. |
| combined | Single-brace JSON examples made `str.format` raise `KeyError` on every render: the `combined_call` strategy could not run. | Braces escaped; definitions aligned with W1-W4. `tests/test_prompts.py` now renders every prompt. |

Not a prompt issue, recorded here because it dominates the state-node numbers:
`evaluation/metrics/state_node_merge.py` matches labels by token Jaccard >= 0.4,
so paraphrases of the same commitment rarely match (e.g. "Use gpu-a100 partition
for training and production runs" vs gold "Run training on the gpu-a100
partition" scores 0.3). State-node creation precision/recall should not be read
as a prompt-quality signal until the matcher is revisited.

## Earlier versions (reconstructed from git on 2026-09-27)

These entries describe what the diffs between the stored versions show; the
reasons behind them were not recorded at the time.

### v3 (2026-09-17, commit `8540c81`)
- W1: entity types come from the conversation's vocabulary (`{allowed_entity_types}`), with `propose:<label>` for types that don't fit; a third few-shot example (the `rest_api` Article/Source one) added.
- W2: three few-shot examples added (implicit supercase, subcase, same_level), the supercase one taken from the `rest_api` corpus.
- W3: "resolves vs depends_on" guidance added.
- W4: unchanged. Combined: small edits; the brace bug from v2 remains.

### v2 (2026-09-08, commit `78bf461`)
- W1-W3: note that `[N_k]` markers in answers are citations, not entities or candidates.
- W1: first two few-shot examples; the fixed type list is replaced by a definition of what counts as an entity.
- W2: first few-shot example (a recap as supercase).
- W4: rewritten; valid statuses per type and terminal statuses spelled out.
- Combined: rewritten; its JSON examples use single braces, so `str.format` fails and `combined_call` cannot run (fixed in v4).

### v1 (2026-09-06, commit `47bed79`)
- Initial W1-W5, combined extraction and answer-generation prompts. W1 has a fixed entity-type list and no few-shot examples; W2 has no examples.

