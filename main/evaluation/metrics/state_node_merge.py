"""Are state nodes created and merged sensibly? (workplan task 3.1)

The Phase 3 readiness checklist explicitly leaves this metric undecided: "a
decision on a validation metric for merge correctness (duplicate state nodes vs.
missed updates to an existing one) once real data is available". This module is
a *proposal*, not a settled metric. Treat the numbers as provisional and revise
the definition once you have annotated data in hand.

The proposal decomposes the question into three counts, because "merge
correctness" is really three distinct failure modes with different causes:

1. **Over-creation (duplicates).** Two state nodes that should be one. Cause:
   the merge instruction in the W4 prompt is too weak, or the open-state-node
   list shown to W4 was truncated.
2. **Under-creation (misses).** A goal/decision/constraint in the gold data that
   no state node covers. Cause: W4 is too conservative, or the turn's phrasing
   does not look like a state-node trigger.
3. **Status errors.** The right node exists but its lifecycle status is wrong.
   Cause: the update instruction, not the create instruction. Fixing (1) or (2)
   will not fix this.

Matching predicted labels to gold ones needs a similarity function. The default
is deliberately crude (token Jaccard) so that the metric has no hidden model
dependency. If you use an embedding-based matcher, say so when you report - it
changes the numbers and it makes the metric depend on the embedder.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class StateNodeRef:
    """A predicted or gold state node."""

    type: str
    label: str
    status: str = "active"


def token_jaccard(a: str, b: str) -> float:
    """Similarity in [0, 1]. No model dependency, fully reproducible."""
    ta = {t for t in a.lower().split() if len(t) > 2}
    tb = {t for t in b.lower().split() if len(t) > 2}
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


@dataclass
class MergeReport:
    matched: list[tuple[StateNodeRef, StateNodeRef]] = field(default_factory=list)
    duplicates: list[StateNodeRef] = field(default_factory=list)
    missed: list[StateNodeRef] = field(default_factory=list)
    status_errors: list[tuple[StateNodeRef, StateNodeRef]] = field(default_factory=list)

    def as_dict(self) -> dict:
        n_gold = len(self.matched) + len(self.missed)
        n_pred = len(self.matched) + len(self.duplicates)
        return {
            "n_gold": n_gold,
            "n_predicted": n_pred,
            "matched": len(self.matched),
            "duplicates": len(self.duplicates),
            "missed": len(self.missed),
            "status_errors": len(self.status_errors),
            "creation_precision": round(len(self.matched) / n_pred, 4) if n_pred else 0.0,
            "creation_recall": round(len(self.matched) / n_gold, 4) if n_gold else 0.0,
            "status_accuracy": round(
                1 - len(self.status_errors) / len(self.matched), 4
            ) if self.matched else 0.0,
            "duplicate_examples": [d.label for d in self.duplicates[:10]],
            "missed_examples": [m.label for m in self.missed[:10]],
        }


def evaluate_state_nodes(
    predicted: list[StateNodeRef],
    gold: list[StateNodeRef],
    *,
    threshold: float = 0.4,
    require_type_match: bool = True,
) -> MergeReport:
    """Greedy one-to-one matching of predicted state nodes to gold ones.

    Greedy rather than optimal (Hungarian) matching: state-node counts per
    conversation are small (tens), the labels are short, and greedy-by-best-score
    is easier to explain in a thesis than an assignment algorithm. If two gold
    nodes are close enough for greedy to matter, they were probably the same node
    and the gold annotation should be fixed.

    ``require_type_match`` on by default: a goal predicted where the gold says
    constraint is a real error, not a near-miss. Turning it off answers the
    separate question "did it find the right *thing*, ignoring the category".
    """
    report = MergeReport()
    unmatched_gold = list(gold)

    for pred in predicted:
        best, best_score = None, 0.0
        for g in unmatched_gold:
            if require_type_match and g.type != pred.type:
                continue
            score = token_jaccard(pred.label, g.label)
            if score > best_score:
                best, best_score = g, score

        if best is not None and best_score >= threshold:
            unmatched_gold.remove(best)
            report.matched.append((pred, best))
            if pred.status != best.status:
                report.status_errors.append((pred, best))
        else:
            # No gold node left for this prediction. Either a genuine spurious
            # node or a duplicate of one already matched - both are the same
            # failure from the user's point of view (an extra node in the graph).
            report.duplicates.append(pred)

    report.missed = unmatched_gold
    return report
