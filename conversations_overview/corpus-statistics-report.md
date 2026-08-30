# Corpus Statistics Report — `conv_01` (REST API Design, N_1–N_50)

**Revision 2** — regenerated after a full audit against the schema spec (`INESCTEC_RESEARCH.pdf` §3.3–3.5). Supersedes revision 1, which reported statistics computed from ground truth containing an unapplied state machine (see §14).

## 1. Overview

| | Count |
|---|---|
| Interaction nodes | 50 |
| State nodes | 56 |
| Entities | 36 |
| Schema findings logged | 8 |
| Validation errors (post-fix) | 0 |

## 2. Hierarchical edges (81 total)

| Label | Count | % |
|---|---|---|
| `subcase` | 54 | 67% |
| `same_level` | 19 | 23% |
| `supercase` | 8 | 10% |
| No relation to any candidate | 2 nodes (N_1, N_15) | — |

`supercase` rose from 3 to 8 after correcting N_36 (the consolidated-review turn). The spec's own W2 few-shot example establishes that a summary spanning several decisions is `supercase` of each, with the goal-setting node it doesn't summarize getting `no_relation` — N_36 had been labelled `[N_1, subcase]`, the opposite pattern. Still the rarest hierarchical label; n=8 is usable but thin.

## 3. Pragmatic edges (90 total)

| Label | Count | % |
|---|---|---|
| `depends_on` | 44 | 49% |
| `references` | 36 | 40% |
| `resolves` | 5 | 6% |
| `revises` | 4 | 4% |
| `contradicts` | 1 | 1% |

`resolves` rose from 1 to 5 after correcting turns that close a previously-raised question but had been labelled `depends_on` (N_47→N_17, N_37→N_36) or carried no edge at all (N_46→N_36, N_38→N_36). `contradicts` remains at n=1 — no further genuine instance exists in this conversation, and manufacturing one would compromise the ground truth.

## 4. `subcase` / `depends_on` overlap

| | Count |
|---|---|
| Same target has both `subcase` and `depends_on` | 36 |
| `subcase` only | 18 |
| `depends_on` only | 8 |

**66.7%** of `subcase` edges also carry `depends_on` to the same target (was 69.1%). The reduction is incidental, not a fix. This remains the corpus's single largest methodological open item: it cannot be resolved by self-audit, since the annotator (Claude) is the same party whose bias is in question. It needs an independent second annotator on a sample, or a sharper operational test in the schema distinguishing "is topically narrower" from "requires the parent's content to be interpretable."

## 5. Epistemic status (corrected)

| Status | Count |
|---|---|
| `resolved` | 43 |
| `superseded` | 4 |
| `open` | 2 |
| `contested` | 1 |

All four spec statuses now occur. Revision 1 reported `resolved: 50` — an artifact of the bug in §14, not a property of the conversation.

Transitions applied by replaying the §3.5 edge→status table in turn order:

| Source | Label | Target | Transition |
|---|---|---|---|
| N_7 | `resolves` | N_6 | open → resolved |
| N_10 | `contradicts` | N_9 | open → **contested** |
| N_21 | `revises` | N_20 | resolved → **superseded** |
| N_26 | `revises` | N_4 | resolved → **superseded** |
| N_32 | `revises` | N_31 | resolved → **superseded** |
| N_38 | `revises` | N_27 | resolved → **superseded** |
| N_37, N_38, N_46 | `resolves` | N_36 | resolved → resolved (no-op, logged for provenance) |
| N_47 | `resolves` | N_17 | resolved → resolved (no-op, logged) |

8 nodes now carry post-creation `epistemic_history` entries (was 1). The four no-op transitions are deliberately logged: the spec requires provenance logging even when the status does not change, which makes them useful negative test cases for Phase 3.1 (a pipeline must log without mutating).

## 6. Entity types (36 total)

| Type | Count |
|---|---|
| `endpoint` | 21 |
| `resource` | 11 |
| `tool` | 3 |
| `system` | 1 |
| `person`, `organization`, `location`, `document`, `measurement`, `event` | **0** |

**Unchanged and unfixable within this corpus.** A REST-API-design conversation genuinely does not mention people, organizations, or locations. Only a second corpus in a different domain can provide coverage here.

## 7. State nodes: type × status (56 total)

| Type | Count | Status breakdown |
|---|---|---|
| `decision` | 43 | 37 active, 6 revised |
| `constraint` | 7 | 7 active |
| `open_question` | 4 | 3 resolved, 1 **open** |
| `goal` | 2 | 1 achieved, 1 active |

SN_51 had been recorded as `active`, which is not a valid status for `open_question` (valid: `open` | `resolved`) — corrected. Still never observed: `constraint: revised`, `constraint: lifted`, `decision: reverted`, `goal: abandoned`.

## 8. `relates` label distribution (64 total)

| Label | Count |
|---|---|
| `supports` | 58 (91%) |
| `constrained_by` | 3 |
| `resolves` | 3 |
| `contradicts` | **0** |

## 9. `state_node_links` activity

| | Count |
|---|---|
| `creates` | 56 |
| `updates` | 10 |
| `relates` | 64 |
| Turns creating >1 state node | 9 |

## 10. Citations

Mean 1.48 per node. Distribution: 0 (4 nodes), 1 (24), 2 (17), 3 (4), 4 (1). Every `citations` entry has a matching `[N_x]` bracket in the answer text and vice versa (automated check, 0 errors).

## 11. Recurrence / retrieval hubs

Mean `recurrence_count`: **3.42**.

| Node | Incoming |
|---|---|
| N_2 | 13 |
| N_3 | 12 |
| N_10 | 11 |
| N_1 | 8 |
| N_27 | 7 |
| N_24 | 7 |

## 12. Speech acts (50 total)

| Speech act | Count |
|---|---|
| `decision` | 37 |
| `request` | 4 |
| `correction` | 2 |
| `factual_question` | 2 |
| `clarification_request` | 2 |
| `information` | 1 |
| `follow_up` | 1 |
| `suggestion` | 1 |
| `agreement`, `disagreement`, `feedback` | **0** |

Six relabels applied where a more specific act was clearly warranted: N_10 and N_38 → `correction` (both answers explicitly correct an earlier conclusion), N_21 → `suggestion`, N_23 and N_29 → `clarification_request` (both open with "I want to clarify"), N_36 → `information` (summary turn, matching the spec's own worked example). Coverage improved from 4 to 8 of 11 acts, but the distribution is still dominated by `decision`.

## 13. What was fixed, and what was not

**Definite bugs (spec violations) — fixed:**
1. Epistemic state machine never applied (§14 below) — 50/50 nodes wrong.
2. `SN_51` carried a status invalid for its type.
3. Four answer texts diverged between `corpus.json` and `ground_truth.json` (quote marks lost to shell escaping).

**Judgment-call relabels — applied, each traceable to a spec precedent:**
4. N_36 hierarchical direction (spec's own W2 few-shot example).
5. Four `resolves` edges that had been `depends_on` or absent.
6. Six speech-act relabels.

**Not fixed, because fixing would mean fabricating data:**
- `contradicts` (n=1 interaction-level, n=0 state-level) — no further genuine instance occurs.
- Six entity types at n=0 — domain artifact.
- Four state-node status values at n=0 — no such events occurred.
- `agreement`, `disagreement`, `feedback` speech acts at n=0.

These gaps are a property of the conversation itself: it was a cooperative design dialogue where the researcher asked and the assistant proposed. Real corpora contain disagreement, abandoned goals, reverted decisions, and lifted constraints. **Closing these gaps requires additional turns, not further relabeling** — and ideally a second conversation in a different domain, both to cover the missing entity types and to reduce the single-domain bias of the whole set.

## 14. Note on revision 1

Revision 1 reported "All 50 nodes: `resolved` in final state" and listed `superseded`/`contested` as never occurring. That was wrong. The conversation did contain the discourse events; the annotation simply never ran the §3.5 transition table, so no status ever changed and only one node had post-creation history. The statistics faithfully described the ground truth, and the ground truth was broken — which is worth recording as a methodological lesson: **a statistics report over unvalidated ground truth will confidently report the annotation's bugs as findings about the data.** Schema-conformance validation must run before, not after, descriptive statistics.

## 15. Coverage summary for Phase 3.1

**Strong (n ≥ 19):** `subcase`, `depends_on`, `references`, `same_level`, `decision` speech act, `supports` relation, `endpoint`/`resource` entity types.

**Usable but thin (n = 4–8):** `supercase` (8), `resolves` (5 interaction / 3 state-level), `revises` (4), `superseded` status (4).

**Not measurable (n ≤ 2):** `contradicts` (1 interaction / 0 state-level), `contested` (1), `open` (2), most speech acts, six entity types, four state-node statuses.

**Recommendation:** report per-label precision/recall with sample size stated inline, and treat n < 5 as qualitative illustration rather than measurement. Consider a second corpus in a contrasting domain before drawing conclusions about the rare labels.
