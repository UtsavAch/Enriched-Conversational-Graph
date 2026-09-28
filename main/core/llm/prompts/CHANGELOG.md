# Prompt changelog

All versions are stored in [`versions/`](versions/README.md) and selectable with
`GM_PROMPT_VERSION=v1|v2|v3|v4|v5|v6`.

## v6 (2026-09-28): uncited callbacks as `references` (W3)

**Problem (v5).** On the held-out testbeds, `references` F1 was 0.080 (44 gold edges). Most gold
`references` there are uncited callbacks ("as we agreed in May"), and v5 labelled many of them
`depends_on` or `no_relation` (see `evaluation/reports/prompt_v5_heldout_evaluation_2026-09-28.md`).

**Change.** W3 gains a hard-case rule: most references have no `[N_k]` marker; a turn that
mentions an earlier one in passing (to remind, compare or give context) and whose own point
stands without it is `references`, not `depends_on` or `no_relation`. Plus a worked example of an
uncited comparison. The same sentence is added to `combined_extraction.txt`. W1, W2 and W4 are
unchanged from v5.

**Evidence (W3-only replay).** W3 v5 and v6 were run on every turn of the six held-out testbeds
with identical candidates (from the stored `<corpus>_gemma4_v5` graphs, same selection code incl.
cited turns), gemma4:31b, 0 failed calls. Pragmatic labels only, pooled over 354 gold edges:

| Label | Gold | v5 F1 | v6 F1 | Change |
|---|---|---|---|---|
| Pragmatic macro | 354 | 0.274 | 0.275 | +0.001 |
| references | 44 | 0.077 | 0.080 | +0.003 |
| depends_on | 201 | 0.366 | 0.378 | +0.012 |
| revises | 26 | 0.203 | 0.226 | +0.023 |
| resolves | 63 | 0.361 | 0.357 | −0.004 |
| contradicts | 20 | 0.361 | 0.333 | −0.027 |

**Result: no measurable effect.** v6 predicts `references` more often (112 → 132) and recall rises
slightly (0.136 → 0.159), but precision stays at about 5%: roughly 125 predicted `references` per
version against 44 gold, of which only about 6-7 match. Per corpus, `references` improved only on
`tutoring_stats` (0 → 0.087) and fell slightly on `thesis_planning` and `relocation`.

**Interpretation.** A 5% precision that no prompt wording moves suggests the gold may under-annotate
`references`: the model may be finding real callbacks that the annotation left as no relation.
Before further prompt work on this label, a manual check of a sample of the predicted
`references` "false positives" is needed to tell model error from annotation gaps. v6 is kept as
the working version because it is neutral overall (no label moves by more than 0.03).

## v5 (2026-09-27): looser W4 constraint definition

**Problem (v4).** On `rest_api`, v4 created no constraints at all (gold: 7). All 7 gold
constraints there are requirements the API design must meet ("internal error details must never
be exposed", "only an explicit whitelist of fields may be updated"), and v4's definition only
counted limits and "a rule someone imposes on this project", excluding "general facts and best
practices".

**Change.** A constraint is now "a condition the plan must satisfy, whatever else is chosen", in
three kinds: (a) limits (budget, deadline, quota, capacity, availability), (b) rules that apply to
the project whoever set them, including documentation it must follow, and (c) requirements phrased
with must / must not / never / only. A decision picks one option; a constraint restricts every
option. Two new examples (a must-never requirement; a council rule plus the decision made under it).
The same definition goes into `combined_extraction.txt`. W1-W3 are unchanged from v4.

**Evidence (W4-only replay).** W4 v4 and v5 were run on every turn of `rest_api` and `hpc_support`
with identical inputs (open state nodes from the stored v4 graphs), gemma4:31b, 200 calls, 0
failures. A gold constraint counts as found if a constraint was created within ±1 turn of it.

| | Gold constraints found | Constraint turns near a gold one | State nodes created |
|---|---|---|---|
| `rest_api` v4 → v5 | 0/7 → **4/7** | 0/0 → 5/12 | 80 → 91 |
| `hpc_support` v4 → v5 | 2/3 → **3/3** | 2/4 → 4/9 | 19 → 24 |

Recall recovers. Many "extra" constraints are requirements the gold annotated as decisions (e.g.
"relationship toggles must use PUT", "conversation messages must be immutable"), so part of the
precision gap is the decision/constraint boundary in the gold itself. The cost: decision counts did
not fall (69 → 69 on `rest_api`), so v5 adds constraints rather than reclassifying decisions, and
total state nodes rise by 14% and 26%. If over-creation matters more than constraint recall, the
next step is to make "a requirement is recorded as a constraint *instead of* a decision" stricter,
or to align the gold's decision/constraint boundary with this definition.

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

