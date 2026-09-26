"""Correctness of edge classification (workplan task 3.1).

Two things are measured, and they answer different questions:

* **Per-relation P/R/F1.** For each label (revises, contradicts, ...), how often
  did the classifier get it right? This is where the thinness problem shows up:
  a label with near-zero support in the gold data is telling you something about
  the corpus, and a label with support but zero recall is telling you something
  about the prompt.
* **The confusion matrix.** *Which* labels get mistaken for which. Far more
  useful for Phase 3 prompt iteration than aggregate F1: knowing that
  ``revises`` is being predicted where gold says ``contradicts`` points straight
  at the part of the prompt that distinguishes cooperative refinement from
  disagreement.

``no_relation`` is treated as a real label throughout. It is the majority class
and excluding it would hide the classifier's most common behaviour - over- or
under-connecting the graph.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

NO_RELATION = "no_relation"

#: The schema's two independent edge families (core/schema/enums.py). A turn can
#: hold one hierarchical AND one pragmatic edge to the same earlier turn (e.g.
#: N_3 -> N_2 subcase + resolves), so every pair is scored once per family.
#: Kept as literals rather than imported from core.schema, so the metrics stay
#: independent of the pipeline (see evaluation/annotation.py).
HIERARCHICAL_LABELS = frozenset({"subcase", "supercase", "same_level"})
PRAGMATIC_LABELS = frozenset({"revises", "contradicts", "resolves", "depends_on", "references"})


def relation_family(label: str) -> str:
    if label in HIERARCHICAL_LABELS:
        return "hierarchical"
    if label in PRAGMATIC_LABELS:
        return "pragmatic"
    return "other"


@dataclass(frozen=True)
class RelationRef:
    """One classified (source, target) pair and the label assigned to it."""

    source: str
    target: str
    relation: str


def _pair_map(refs: list[RelationRef]) -> dict[tuple[str, str, str], str]:
    """Key each edge by (source, target, family), not (source, target).

    Keying by pair alone let a pragmatic label overwrite the hierarchical label
    on the same pair, silently dropping it from both gold and predictions
    (65 of 171 gold relations on rest_api).
    """
    return {(r.source, r.target, relation_family(r.relation)): r.relation for r in refs}


def confusion_matrix(
    predicted: list[RelationRef], gold: list[RelationRef], family: str | None = None
) -> dict[str, dict[str, int]]:
    """``matrix[gold_label][predicted_label] = count``.

    The union of (pair, family) keys appearing in either list is scored. A pair
    the classifier did not mention in a family is treated as ``no_relation`` in
    that family - which is exactly what it meant, since the prompts instruct it
    to omit no-relation pairs. Labels never cross families, so e.g. a predicted
    ``subcase`` where gold has only ``resolves`` is a hierarchical false positive
    plus a pragmatic false negative, not a subcase/resolves confusion.

    ``family`` ("hierarchical" / "pragmatic") restricts the matrix to one family.
    """
    pred, gld = _pair_map(predicted), _pair_map(gold)
    matrix: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for key in set(pred) | set(gld):
        if family is not None and key[2] != family:
            continue
        matrix[gld.get(key, NO_RELATION)][pred.get(key, NO_RELATION)] += 1
    return {g: dict(row) for g, row in matrix.items()}


def _macro(rows: list[dict[str, float]]) -> dict[str, float]:
    return {
        "precision": round(sum(v["precision"] for v in rows) / len(rows), 4) if rows else 0.0,
        "recall": round(sum(v["recall"] for v in rows) / len(rows), 4) if rows else 0.0,
        "f1": round(sum(v["f1"] for v in rows) / len(rows), 4) if rows else 0.0,
        "support": sum(v["support"] for v in rows),
    }


def per_relation_prf(
    predicted: list[RelationRef], gold: list[RelationRef]
) -> dict[str, dict[str, float]]:
    """P/R/F1 for every label present in either list, plus a macro average.

    Macro rather than micro average, deliberately: micro would be dominated by
    ``no_relation``, which is the majority class by a wide margin, and would
    make a classifier that never predicts an edge look excellent.
    """
    matrix = confusion_matrix(predicted, gold)
    labels = set(matrix) | {p for row in matrix.values() for p in row}
    out: dict[str, dict[str, float]] = {}

    for label in sorted(labels):
        tp = matrix.get(label, {}).get(label, 0)
        fn = sum(v for k, v in matrix.get(label, {}).items() if k != label)
        fp = sum(row.get(label, 0) for g, row in matrix.items() if g != label)
        precision = tp / (tp + fp) if (tp + fp) else 0.0
        recall = tp / (tp + fn) if (tp + fn) else 0.0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
        out[label] = {
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1": round(f1, 4),
            "support": tp + fn,
        }

    scored = {k: v for k, v in out.items() if k != NO_RELATION}
    out["macro_avg_excl_no_relation"] = _macro(list(scored.values()))
    # Per-family macro averages: the two families are different tasks (topic
    # structure vs discourse function) and are worth reporting separately.
    out["macro_avg_hierarchical"] = _macro(
        [v for k, v in scored.items() if relation_family(k) == "hierarchical"]
    )
    out["macro_avg_pragmatic"] = _macro(
        [v for k, v in scored.items() if relation_family(k) == "pragmatic"]
    )
    return out


def resolution_linking_accuracy(
    predicted: list[RelationRef], gold: list[RelationRef]
) -> dict[str, float]:
    """Do ``resolves`` edges connect open questions to their actual answers?

    Called out separately in the workplan (task 4.3) because it is the single
    relation with a directly checkable semantics: an open question either did or
    did not get linked to the turn that settled it. Aggregate relation F1 buries
    this; a resolves-specific number does not.
    """
    pred = {(r.source, r.target) for r in predicted if r.relation == "resolves"}
    gld = {(r.source, r.target) for r in gold if r.relation == "resolves"}
    if not gld:
        return {"precision": 0.0, "recall": 0.0, "gold_count": 0}
    tp = len(pred & gld)
    return {
        "precision": round(tp / len(pred), 4) if pred else 0.0,
        "recall": round(tp / len(gld), 4),
        "gold_count": len(gld),
    }
