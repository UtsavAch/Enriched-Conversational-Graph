# Corpus Statistics Report — `tech_support` (Email Delivery Reliability, N_1–N_26)

**Revision 1** — generated at draft time, immediately after automated consistency validation (all
checks passed on first re-run after one bookkeeping fix). Unlike `conv_01`'s report, this one
predates a manual audit rather than following one — see §9.

## 1. Overview

| | Count |
|---|---|
| Interaction nodes | 26 |
| State nodes | 11 |
| Entities | 7 |
| Schema findings logged | 2 |
| Automated consistency errors (post-fix) | 0 |

Built specifically to fill gaps `conv_01`'s own stats report flagged as unfixable within that
corpus: `contradicts` (n=1 there, "manufacturing one would compromise the ground truth"), and
several state-node status values never observed there at all (`constraint: revised/lifted`,
`decision: reverted`, `goal: abandoned`). See `evaluation_report.md`, "Build the technical support
corpus" for the design rationale and target-label mapping this corpus was built against.

## 2. Hierarchical edges (10 total)

| Label | Count | % |
|---|---|---|
| `supercase` | 7 | 70% |
| `same_level` | 2 | 20% |
| `subcase` | 1 | 10% |

Deliberately supercase-heavy, the inverse of `conv_01`'s distribution (there: 67% `subcase`, 10%
`supercase`) — intentional, since `supercase` was the harder label to get right in prompt
iteration (`evaluation_report.md` §13) and this corpus exists partly to give it more support.
6 of the 7 `supercase` edges come from one explicit review turn (N_24 → N_6/N_7/N_13/N_16/N_17/
N_18), matching `conv_01`'s own N_36 pattern; the 7th (N_7 → N_6) is the other pattern — an
implicit generalisation with no "let me summarize" framing, the specific gap identified in
`evaluation_report.md` §13's diagnosis of the original prompt's blind spot. `subcase` is
intentionally thin (n=1) here — this corpus's density is on the labels `conv_01` under-supports,
not a re-run of what it already covers well.

## 3. Pragmatic edges (23 total)

| Label | Count | % |
|---|---|---|
| `depends_on` | 11 | 48% |
| `resolves` | 4 | 17% |
| `revises` | 3 | 13% |
| `references` | 3 | 13% |
| `contradicts` | 2 | 9% |

`contradicts` at n=2 is the headline number this corpus exists to produce — `conv_01` had exactly
1, flagged as a corpus-scarcity ceiling, not an annotation gap. Both instances here are genuine
disputes with evidence (N_4 disputing the spam-filtering diagnosis with direct user reports; N_17
disputing the "isolated to one email" assumption by finding the same bug elsewhere), each
followed by a `resolves` edge that settles the dispute in the following turn.

## 4. `subcase` / `depends_on` overlap

| | Count |
|---|---|
| Same target has both `subcase` and `depends_on` | 0 |
| `subcase` only | 1 |
| `depends_on` only | 11 |

**0% overlap** — a deliberate methodological check against `conv_01`'s flagged 67% overlap (which
that corpus's own report called "the single largest methodological open item," needing "a sharper
operational test... distinguishing 'is topically narrower' from 'requires the parent's content to
be interpretable'"). This corpus's one `subcase` edge (N_9 → N_8) and its eleven `depends_on`
edges were assigned independently with that distinction actively in mind, and land on completely
disjoint pairs. Not proof the distinction is now well-defined in general (n=1 subcase is too thin
to draw a real conclusion from), but at minimum this corpus doesn't reproduce the same conflation.

## 5. Epistemic status

| Status | Count |
|---|---|
| `resolved` | 20 |
| `superseded` | 3 |
| `open` | 2 |
| `contested` | 1 |

All four values occur. The single `contested` (N_15) is a node whose `resolves` edge (from N_18)
arrives and clears it back to `resolved` per the spec's state-dependent transition table — worth
a specific check when this corpus is used to validate the pipeline's epistemic-status propagation,
since `conv_01`'s worked audit didn't have a `contested`→`resolved` transition to exercise (it had
`open`→`contested` and `revises`-driven `superseded` transitions, but not this specific one).

## 6. Entity types (7 total)

| Type | Count |
|---|---|
| `system` | 2 |
| `tool` | 2 |
| `document` | 2 |
| `feature` | 1 |
| `person`, `organization`, `location`, `measurement`, `event`, `other` | **0** |

One domain-specific type added beyond the default set: `feature` (the "Resend email" button) —
deliberately just one, versus `conv_01`'s two (`resource`, `endpoint`), per the "keep it simple"
brief this corpus was built under. Coverage is narrower than `conv_01`'s by design (a 26-turn,
single-scenario corpus doesn't need to exercise every entity type) — combining both corpora for
any future cross-corpus entity-type evaluation would still leave `person`/`organization`/
`location` uncovered entirely; a third corpus would need to target those specifically if that
matters later.

## 7. State nodes: type × status (11 total)

| Type | Count | Status breakdown |
|---|---|---|
| `decision` | 5 | 2 active, 2 revised, 1 reverted |
| `goal` | 3 | 1 active, 1 achieved, 1 abandoned |
| `open_question` | 2 | 1 open, 1 resolved |
| `constraint` | 1 | 1 lifted |

Every status value for every type now has at least one instance **across the two corpora
combined** — `conv_01` alone was missing `constraint: revised`, `constraint: lifted`,
`decision: reverted`, and `goal: abandoned` entirely; this corpus supplies `decision: reverted`
(SN_7), `goal: abandoned` (SN_5), and `constraint: lifted` (SN_6). `constraint: revised` is still
unrepresented in either corpus — the one gap that survives combining both.

## 8. `relates` label distribution (6 total)

| Label | Count |
|---|---|
| `contradicts` | 2 |
| `supports` | 2 |
| `resolves` | 1 |
| `constrained_by` | 1 |

Notably thin compared to `conv_01`'s 64 `relates` edges — proportionally similar though (6/26 ≈
0.23/turn here vs. 64/50 ≈ 1.28/turn there is a real difference, not just scale; this corpus
favours direct `updates` for terminal status changes like `abandoned`/`reverted`/`lifted`, which
have no corresponding `StateRelation` label and so are recorded via `state_node_links.updates`
alone — see the `schema_findings` entry on this in `ground_truth.json` itself).

## 9. `state_node_links` activity

| | Count |
|---|---|
| `creates` | 11 |
| `updates` | 7 |
| `relates` | 6 |

11 creates matches the 11 state nodes exactly (one creation turn each, no duplicates by
construction). 7 updates: 2 status-only revisions (SN_2, SN_10), 1 resolved (SN_3), 1 abandoned
(SN_5), 1 lifted (SN_6), 1 reverted (SN_7), 1 achieved (SN_1) — every state node except the two
left deliberately untouched after creation (SN_8, SN_9) and the one left open (SN_11) has exactly
one status-changing update, reflecting this corpus's relatively linear "problem → diagnosis →
correction → fix" structure rather than `conv_01`'s more iterative back-and-forth on a smaller
number of long-lived decisions.

## 10. Citations

6 citation instances across 4 nodes (N_7→[N_6], N_13→[N_10], N_19→[N_7], N_24→[N_6,N_13,N_16]).
Automated check confirms every `[N_x]` bracket marker in answer text has a matching `citations`
entry and vice versa (see §11 below) — `conv_01`'s own report flagged this exact check as
something that had to be caught manually and fixed with a post-commit check going forward; this
corpus's automated verification script (used during construction, not a separate later fix) is
that same check applied from the start rather than retrofitted.

## 11. Recurrence hubs

Top 5 by `recurrence_count`: N_6 (5), N_2 (3), N_16 (3), N_4 (2), N_7 (2). N_6 — the turn that
finds the real root cause (MailBridge rate-limiting) and switches to SendClear — is the single
most-referenced node in the corpus, which matches its narrative role as the pivot the `contradicts`
→ `revises` → `resolves` chain converges on.

## 12. Speech acts (26 total)

| Act | Count |
|---|---|
| `information` | 10 |
| `request` | 6 |
| `clarification_request` | 3 |
| `follow_up` | 3 |
| `correction` | 2 |
| `agreement` | 2 |

No `decision`, `suggestion`, `feedback`, `disagreement`, or `factual_question` instances — this
corpus's dialogue register leans toward the user reporting/confirming information and the agent
diagnosing, rather than either side explicitly hedging with a `suggestion` or bluntly
`disagreement`-ing. Worth noting if speech-act-distribution matching against real support
transcripts ever matters: this is a narrower register than a fully naturalistic transcript would
likely have.

## 13. Automated verification performed

Unlike `conv_01` (manually audited against the schema spec after initial construction, per that
corpus's own revision history), this corpus was checked with a purpose-written script at
construction time, covering: corpus/ground-truth text equality, edge target existence and
backward-in-time direction, state-node reference validity, bidirectional entity mention
consistency, citation-bracket/field consistency, recurrence-count correctness, state-node status
validity per type, `StateRelation` label validity, hierarchical/pragmatic label validity,
speech-act validity, entity-type validity, and state-node creation/update provenance consistency.
One error found and fixed (a `recurrence_count` off-by-one on N_14). All checks pass as of this
report.

**What this does not replace**: automated structural consistency is not the same as a human
judging whether the *content* is realistic, whether an edge label is the *right* label for what's
actually being said, or whether the story is genuinely representative of technical support
dialogue. That review is still pending — see `evaluation_report.md`'s note that this corpus is
"ready for you to read directly and correct anything" before conversion/ingestion proceeds.

## 14. Coverage summary against the corpus's stated purpose

| Target (from the build plan) | Status |
|---|---|
| `contradicts` ≥ 1 genuine instance | ✅ 2 |
| `supercase`, both patterns (explicit review + implicit generalisation) | ✅ both present |
| `decision: reverted` | ✅ SN_7 |
| `goal: abandoned` | ✅ SN_5 |
| `constraint: lifted` | ✅ SN_6 |
| Simple, non-jargon domain | Subjective — pending your read |
| Smaller than `conv_01` (quota lesson) | ✅ 26 turns vs. 50 |

Every structural target this corpus was built to hit is present and automatically verified. The
one still-open item, `constraint: revised` (never occurring in either corpus), wasn't part of
this corpus's target list and remains a gap for a future corpus if it matters.