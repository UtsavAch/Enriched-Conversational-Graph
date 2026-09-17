"""LLM-as-judge scoring for consistency probes (pipeline design step 12; workplan 4.3).

`consistency.py` already lays out the tradeoff and the rule this module
follows: "Start with keyword probes. Only move to a judge when you can show
keyword matching is the binding limitation, and report both if you do." This
module is deliberately narrow because of that rule - it is not a general
answer-quality judge, only a second opinion on the specific probes where
`score_keyword_probe` already failed. A keyword failure is either a real
inconsistency or a paraphrase the keyword list didn't anticipate; the judge
exists to tell those two apart, not to re-score probes that already passed.

HONEST LIMITATION, restated from `consistency.py`: the judge is itself a
model call with its own failure modes (it can be fooled the same way the
extraction pipeline can). Report the judge model and use greedy decoding
(temperature 0) so a result is at least reproducible run-to-run, and always
report the keyword outcome alongside the judge verdict rather than replacing
one with the other.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Protocol

from evaluation.metrics.consistency import ConsistencyProbe, ProbeOutcome

_SYSTEM = (
    "You are checking whether an answer is consistent with a decision that was "
    "previously established in a conversation. You are not judging answer "
    "quality in general - only whether the answer respects, contradicts, or is "
    "silent about the specific decision given to you.\n\n"
    'Respond with JSON only: {"verdict": "consistent" | "contradicts" | '
    '"unclear", "rationale": "<one sentence>"}.\n'
    '- "consistent": the answer\'s content matches or logically follows the decision.\n'
    '- "contradicts": the answer states or implies something the decision rules out.\n'
    '- "unclear": the answer does not engage with the decision either way.'
)


class JudgeClient(Protocol):
    """The minimal shape this module needs - matches `core.llm.client.LLMClient`.

    Typed as a local Protocol rather than importing that class, so this module
    keeps the package's stated property: metrics take plain data (and, here, a
    duck-typed client) and never hard-depend on the pipeline.
    """

    def complete(
        self, system: str, user: str, *, max_tokens: int = 1024, temperature: float = 0.0
    ) -> object: ...  # returns anything with a `.text: str` attribute


@dataclass
class JudgeVerdict:
    probe_id: str
    judge_model: str
    verdict: str  # "consistent" | "contradicts" | "unclear" | "error"
    rationale: str
    raw_response: str

    def as_dict(self) -> dict:
        return {
            "probe_id": self.probe_id,
            "judge_model": self.judge_model,
            "verdict": self.verdict,
            "rationale": self.rationale,
        }


def should_judge(keyword_outcome: ProbeOutcome) -> bool:
    """Escalate to the judge only where the keyword check already failed.

    A pass is never re-judged: `consistency.py`'s own rule is that the judge
    is for the keyword check's documented failure mode (paraphrase), not a
    second, competing scorer run over everything.
    """
    return not keyword_outcome.passed


def judge_consistency(
    client: JudgeClient,
    probe: ConsistencyProbe,
    decision_text: str,
    answer: str,
    *,
    model_name: str,
) -> JudgeVerdict:
    """Ask the judge whether ``answer`` is consistent with ``decision_text``.

    ``decision_text`` is the gold state node's label/content the probe targets
    (``probe.target``, resolved by the caller) - the judge is given the
    decision directly rather than asked to recall it from the conversation,
    since recall accuracy is the extraction pipeline's job, not the judge's.
    """
    user = (
        f"Decision previously established: {decision_text}\n\n"
        f"Question asked: {probe.question}\n\n"
        f"Answer given: {answer}\n\n"
        "Is the answer consistent with the decision?"
    )
    response = client.complete(system=_SYSTEM, user=user, max_tokens=200, temperature=0.0)
    raw = getattr(response, "text", str(response))

    try:
        parsed = json.loads(raw)
        verdict = parsed.get("verdict", "unclear")
        rationale = parsed.get("rationale", "")
    except (json.JSONDecodeError, AttributeError):
        verdict, rationale = "error", f"could not parse judge response: {raw[:200]!r}"

    if verdict not in ("consistent", "contradicts", "unclear"):
        verdict = "error"

    return JudgeVerdict(
        probe_id=probe.probe_id,
        judge_model=model_name,
        verdict=verdict,
        rationale=rationale,
        raw_response=raw,
    )
