"""Precision / recall / F1 of entity extraction (workplan task 3.1).

The hard part of this metric is not the arithmetic - it is deciding what counts
as a match. Three choices are offered, and WHICH ONE YOU REPORT MATTERS, because
they can differ by 20 points on the same output:

* ``exact``      - normalised surface form must match exactly. Strictest.
                   Penalises "the Phase 1-2 report" vs "Phase 1-2 report".
* ``normalised`` - lowercase, strip punctuation and leading articles. Default.
                   Forgives cosmetic differences, still penalises real misses.
* ``typed``      - normalised name AND type must both match. Strictest overall;
                   use it when you specifically want to evaluate typing.

Report the criterion alongside the number. A precision figure without its
matching criterion is not interpretable.
"""

from __future__ import annotations

import re
import string
from dataclasses import dataclass

_ARTICLES = re.compile(r"^(the|a|an|our|my|their)\s+", re.IGNORECASE)
_PUNCT = str.maketrans("", "", string.punctuation)


@dataclass(frozen=True)
class EntityRef:
    """A predicted or gold entity mention, scoped to the turn it appears in.

    Scoping to a turn matters: extracting "INESC TEC" in turn 1 when the gold
    annotation has it in turn 3 is a miss *and* a false positive, not a hit.
    Ignoring turn scope would inflate recall on any conversation that repeats
    entities, which is most of them.
    """

    turn_id: str
    name: str
    type: str = ""


def normalise(name: str) -> str:
    name = name.strip().lower().translate(_PUNCT)
    name = _ARTICLES.sub("", name)
    return re.sub(r"\s+", " ", name).strip()


def _key(ref: EntityRef, criterion: str) -> tuple:
    if criterion == "exact":
        return (ref.turn_id, ref.name.strip().lower())
    if criterion == "typed":
        return (ref.turn_id, normalise(ref.name), ref.type)
    return (ref.turn_id, normalise(ref.name))


@dataclass
class PRF:
    precision: float
    recall: float
    f1: float
    true_positives: int
    false_positives: int
    false_negatives: int
    criterion: str

    def as_dict(self) -> dict:
        return {
            "criterion": self.criterion,
            "precision": round(self.precision, 4),
            "recall": round(self.recall, 4),
            "f1": round(self.f1, 4),
            "tp": self.true_positives,
            "fp": self.false_positives,
            "fn": self.false_negatives,
        }


def entity_prf(
    predicted: list[EntityRef], gold: list[EntityRef], criterion: str = "normalised"
) -> PRF:
    """Compute P/R/F1 over entity mentions.

    Uses set semantics: a duplicate prediction of the same entity in the same
    turn counts once. That is the right call because the schema deduplicates
    entities per conversation anyway, so a repeated extraction is not an
    additional error, it is the same one.
    """
    pred_keys = {_key(p, criterion) for p in predicted}
    gold_keys = {_key(g, criterion) for g in gold}

    tp = len(pred_keys & gold_keys)
    fp = len(pred_keys - gold_keys)
    fn = len(gold_keys - pred_keys)

    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0

    return PRF(precision, recall, f1, tp, fp, fn, criterion)


def error_examples(
    predicted: list[EntityRef], gold: list[EntityRef], criterion: str = "normalised", limit: int = 20
) -> dict[str, list[str]]:
    """The actual false positives and false negatives, for the error analysis.

    Phase 3's deliverable is "a validation report with error analysis and
    examples of failure modes" - not a table of numbers. This function exists so
    that report writes itself from the run rather than from manual grepping.
    """
    pred_map = {_key(p, criterion): p for p in predicted}
    gold_map = {_key(g, criterion): g for g in gold}

    fps = [f"{p.turn_id}: '{p.name}' ({p.type})" for k, p in pred_map.items() if k not in gold_map]
    fns = [f"{g.turn_id}: '{g.name}' ({g.type})" for k, g in gold_map.items() if k not in pred_map]
    return {"false_positives": fps[:limit], "false_negatives": fns[:limit]}
