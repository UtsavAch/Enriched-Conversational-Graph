# Testbed outlines (7 new corpora)

Draft outlines for review **before** writing any `build.py` / `corpus.json` /
`ground_truth.json`. Each outline lives next to where its corpus will go:
`conversations/<id>/outline.md`.

| # | id | Domain | Turns | Main target | Outline |
|---|---|---|---|---|---|
| 1 | `tutoring_stats` | Tutoring: intro statistics | 50 | supercase trees, misconception `contradicts` → `revises` | [outline](tutoring_stats/outline.md) |
| 2 | `hpc_support` | Document-grounded HPC onboarding | 50 | `references`/`cites` to doc sections, `resolves` chains, `constraint: lifted` | [outline](hpc_support/outline.md) |
| 3 | `thesis_planning` | Multi-week thesis planning | 80 | `decision: reverted` then revisited, `goal: abandoned`, long gaps | [outline](thesis_planning/outline.md) |
| 4 | `ml_debugging` | ML model debugging | 50 | dense `contradicts`, hypotheses as open questions, epistemic churn | [outline](ml_debugging/outline.md) |
| 5 | `kitchen_reno` | Kitchen renovation on a budget | 50 | numeric constraints revised repeatedly, stale-number probes | [outline](kitchen_reno/outline.md) |
| 6 | `relocation` | Relocating abroad | 80 | interleaved threads (`same_level`), cross-thread `depends_on`, 20+ turn returns | [outline](relocation/outline.md) |
| 7 | `product_rename` | Product launch with mid-conversation rename | 50 | vocabulary drift / alias entities, anti-semantic-RAG probes | [outline](product_rename/outline.md) |

## Shared conventions (same as `marathon_trip/build.py`)

- **Authored per turn:** `q`, `a`, `act` (speech act), `ents`, `cites`, `hier`, `prag`,
  `creates`, `updates`, `relates`. Everything else (`recurrence_count`,
  `epistemic_status`/history, `mentioned_in`, state-node status and `last_updated_turn`)
  is **derived by code**, never hand-written.
- **Edge direction:** labels describe the NEW turn relative to the CANDIDATE (earlier) turn.
  `subcase` = new is narrower, `supercase` = new is broader, `same_level` = parallel.
- **State-node lifecycles** follow `core/schema/enums.py`: decision `active → revised* →
  reverted`, constraint `active → revised* → lifted`, goal `active → achieved|abandoned`,
  open_question `open → resolved`. Terminal statuses block further updates. So a decision
  that is "brought back" after being reverted is a **new** state node, not a re-activation.
- **Outline notation** in the turn tables:
  `H:` hierarchical edges, `P:` pragmatic edges, `S:` state-node events
  (`+SN_k` create, `SN_k→revised` update, `~SN_k supports|contradicts|constrained_by|resolves` relates).
  Turns written as ranges (e.g. `N_12–N_14`) get one row per turn when the `build.py` is written;
  the range row states the edge pattern each one follows.

## Probe design rule (the fix for "every profile scores 4/4")

Each corpus has **8–10 probes** (up from 4). At least half are tagged with the retrieval
condition they're designed to defeat:

- **[anti-recency]:** the answer was settled far back and never repeated, or a later turn
  mentions the topic with a *stale* value.
- **[anti-semantic]:** the most similar-sounding turn gives the *superseded* answer; the
  current one is phrased differently.
- **[anti-hierarchical]:** the correct answer is reachable only via a pragmatic edge
  (`revises`/`contradicts`/`resolves`), not via topic structure.

`expected_any` / `forbidden_any` are drafts; tighten them once the actual answer text exists.

## Planned label budget (gold, all 7 combined)

| Label | Existing 3 corpora (approx.) | Planned new 7 | Total |
|---|---|---|---|
| `subcase` | ~31 | ~158 | ~189 |
| `same_level` | ~20 | ~48 | ~68 |
| `supercase` | ~14 | ~60 | ~74 |
| `depends_on` | ~70 | ~183 | ~253 |
| `references` | ~45 | ~58 | ~103 |
| `resolves` | ~16 | ~68 | ~84 |
| `revises` | ~8 | ~30 | ~38 |
| `contradicts` | ~3 | ~30 | ~33 |
| `decision: reverted` | ~1 | 10 | ~11 |
| `goal: abandoned` | 0 | 1 | 1 |
| `constraint: lifted` | ~2 | 5 | ~7 |
| `constraint: revised` | ~1 | 7 | ~8 |

(New-corpus numbers are the sums of each outline's "Label targets" line.)

The main point: `contradicts`, `revises` and `supercase` go from single digits to 30–75,
so their per-label F1 becomes a real number rather than noise. Still thin: `goal: abandoned`
(only `thesis_planning`). If it matters, add one to `relocation` (e.g. Sofia's plan to keep
her Lisbon job remotely is abandoned).

## Build order suggestion

2 (`hpc_support`; also needs the doc set written first) → 4 → 7 → 1 → 5 → 3 → 6.
The two 80-turn corpora (3, 6) are last because they take the most annotation effort.
