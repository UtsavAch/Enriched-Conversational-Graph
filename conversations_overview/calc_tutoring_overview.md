# Calculus Tutoring — Conversation Overview

**File:** `calc_tutoring_system_input.jsonl`
**135 QA pairs (interactions) / 270 turns**, spanning **2026-09-02 → 2027-09-25**.

## What this is

A third domain, deliberately different from the two dam-monitoring
conversations: a single student, Leo, working with an AI tutor through
Calculus I, Calculus II, and the start of Calculus III over roughly
thirteen months. Same design principles as Vale Escuro / Vale Nogueira —
no procedurally generated filler, flexible speaker roles, genuine
multi-step learning arcs rather than a bank of independent Q&A pairs.

**Why education, and why this particular structure matters:** engineering
monitoring conversations are mostly specific-case-driven, which is part of
why `supercase` (generalizing upward) barely fired in the dam datasets.
Tutoring is the opposite — "here's a worked example" → "here's the general
rule this is an instance of" is one of the most natural moves a tutor
makes, so this conversation exercises that relation type far more than
either dam conversation does.

## The core arcs

Nine substantive learning threads, each following the same real pattern —
struggle, diagnosis, targeted response, resolution — rather than a
question immediately followed by a correct answer:

1. **Chain rule** (Sep 2026) — the same "forgot the inner derivative"
   error recurs twice before the general rate-of-change framing (not more
   drilling) actually fixes it.
2. **Related rates** (Oct 2026) — the real difficulty is word-problem
   setup, not the calculus; a deliberate decision to practice the two
   skills separately resolves it.
3. **Implicit differentiation** (Nov 2026) — a practice-exam gap analysis
   correctly identifies this as an *untaught* topic rather than a
   weakness, and it turns out to be the September chain rule again in a
   new form.
4. **Optimization** (Nov–Dec 2026) — a genuine synthesis of the two prior
   skills (setup + derivative mechanics) plus one new piece, the second
   derivative test.
5. **Integration & the Fundamental Theorem of Calculus** (Jan–Feb 2027) —
   framed explicitly as the *reverse* of everything from semester one.
6. **U-substitution — the long-range payoff arc** (Feb 2027): this is
   literally the chain rule read backwards, and the *same* error
   (missing the inner-derivative factor) resurfaces, five months later,
   in the reverse direction. The resolution explicitly compares how much
   faster and more independently the student catches it this time —
   evidence the original fix generalized rather than being memorized for
   one unit.
7. **Area between curves** (Mar 2027) — the related-rates setup lesson
   ("sketch before you write an equation") transfers to a new problem
   type.
8. **End-of-year synthesis** (May 2027) — ties every arc together
   explicitly, `depends_on` the resolution of all four prior threads at
   once.
9. **Calculus III begins** (Sep 2027) — a genuinely *new* kind of
   difficulty (geometric intuition for infinite series) that is
   explicitly *not* the old chain-rule-shaped pattern resurfacing —
   deliberately included so the conversation doesn't imply every future
   struggle traces back to the same root cause.

## Light interactions

95 of them — homework spot-checks, `[QUIZ PLATFORM]` automated grade/
reminder messages (the `system`-initiated role here), tangential curiosity
questions ("who invented calculus"), study-schedule logistics, a study
-group friend's question relayed secondhand, a parent's question the
assistant correctly declines to answer (no visibility into class
averages) — genuinely varied, not templated, same principle as the dam
conversations' light layer.

## State nodes populated

- **3 Goals** (Calc I, Calc II, Calc III — the third still ongoing at the
  conversation's end)
- **1 Decision** (the separated setup/mechanics practice plan)
- **1 Constraint** (the 6-week midterm pacing constraint, stated once,
  active throughout)
- **8 Open Questions** — 7 resolved, 1 (the infinite-series intuition
  question raised in the final session) deliberately left open, matching
  the established pattern of not resolving every thread by the
  conversation's end.

## Known limitations

Same caveats as the dam conversations: silver-standard (single-annotator)
relation labels if you build the gold/candidate-pool layer later,
synthetic dialogue rather than a real tutoring transcript, and one
conversation — not enough alone for aggregate statistical comparison.
Mathematical content was written carefully for correctness, but treat it
as illustrative dialogue, not a verified problem set.
