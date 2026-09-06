"""Does the enriched memory keep the agent consistent? (workplan task 4.3)

This is the metric closest to the project's actual motivation. Everything else
measures whether extraction is *correct*; this measures whether it is *useful* -
whether tracking goals, decisions and constraints stops the agent contradicting
a decision it made forty turns ago.

The design is a probe set. For a conversation with known decisions, you write
questions whose correct answer depends on remembering one of them, and check
whether the answer is consistent with the recorded decision.

HONEST LIMITATION: judging "is this answer consistent with decision X" is itself
a judgement call. Two options are supported and they have different threats to
validity:

* ``keyword``    - check for expected/forbidden strings. Fully reproducible, no
                   model in the loop, but brittle and only works for decisions
                   with a crisp lexical signature ("all five" vs "just two").
* ``llm_judge``  - ask a model. Handles paraphrase, but introduces a judge whose
                   own biases become a threat to validity. If used, report the
                   judge model and use greedy decoding, as the thesis does.

Start with keyword probes. Only move to a judge when you can show keyword
matching is the binding limitation, and report both if you do.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ConsistencyProbe:
    """One question whose answer must respect a previously-established item."""

    probe_id: str
    question: str
    #: The state node or decision this probe tests.
    target: str
    #: Answer must contain at least one of these (case-insensitive).
    expected_any: list[str] = field(default_factory=list)
    #: Answer must contain none of these. Catches the reverted-decision failure.
    forbidden_any: list[str] = field(default_factory=list)
    #: Turn index after which the probe is valid (the decision must exist first).
    valid_from_turn: int = 0


@dataclass
class ProbeOutcome:
    probe_id: str
    passed: bool
    answer: str
    reason: str


def score_keyword_probe(probe: ConsistencyProbe, answer: str) -> ProbeOutcome:
    """Evaluate one probe by string matching.

    Fails on a forbidden term even if an expected term is also present: an
    answer that says "we kept all five, though we considered just two" is
    ambiguous, and ambiguity on a consistency probe should be a fail, not a pass.
    Making the strict choice explicit here rather than burying it is what lets a
    reader judge whether the numbers are fair.
    """
    lowered = (answer or "").lower()

    hit_forbidden = [t for t in probe.forbidden_any if t.lower() in lowered]
    if hit_forbidden:
        return ProbeOutcome(probe.probe_id, False, answer, f"contradicted: {hit_forbidden}")

    if probe.expected_any:
        hit_expected = [t for t in probe.expected_any if t.lower() in lowered]
        if not hit_expected:
            return ProbeOutcome(
                probe.probe_id, False, answer, f"missing any of {probe.expected_any}"
            )
        return ProbeOutcome(probe.probe_id, True, answer, f"matched: {hit_expected}")

    return ProbeOutcome(probe.probe_id, True, answer, "no forbidden terms present")


def aggregate(outcomes: list[ProbeOutcome]) -> dict:
    """Pass rate plus the failures themselves, for error analysis."""
    if not outcomes:
        return {"n": 0, "pass_rate": 0.0, "failures": []}
    passed = sum(1 for o in outcomes if o.passed)
    return {
        "n": len(outcomes),
        "passed": passed,
        "pass_rate": round(passed / len(outcomes), 4),
        "failures": [
            {"probe_id": o.probe_id, "reason": o.reason, "answer": o.answer[:200]}
            for o in outcomes
            if not o.passed
        ],
    }
