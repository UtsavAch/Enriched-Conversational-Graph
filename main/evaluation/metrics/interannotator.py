"""Inter-annotator agreement between two independent gold annotations.

The other metrics in this package all answer "how good is the pipeline",
comparing a *prediction* against a single trusted gold file. This module
answers a different, prior question: "how much should we trust that gold file
in the first place" - by comparing it against a second, independent
annotation of the same turns.

This exists because of a concrete, named gap: `conversations_overview/
corpus-statistics-report.md` (revision 2) flags that 66.7% of `subcase` edges
in the `rest_api` corpus also carry `depends_on` to the same target, and says
this "cannot be resolved by self-audit, since the annotator (Claude) is the
same party whose bias is in question. It needs an independent second
annotator on a sample." This module is that check.

Workflow (see the Phase 3 plan): sample ~20% of a corpus's turns, have a
*different* model/provider annotate entities and relations for just those
turns from the raw transcript (no access to the first annotation), save it in
the same flat shape as a `GoldAnnotation` spot-check file, then compare here.

Two numbers are reported, because they answer different questions:

* **Percent agreement** - simple, always computable, easy to misread as
  "reliability" when the label distribution is skewed (e.g. `no_relation`
  dominates, so two annotators can agree 90% of the time by both defaulting
  to it).
* **Cohen's kappa** - corrects for exactly that chance-agreement inflation.
  Use kappa as the headline number; report percent agreement alongside it so
  a reader can see how much of the raw agreement kappa discounted.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

from evaluation.metrics.entity_prf import EntityRef, normalise
from evaluation.metrics.relation_accuracy import NO_RELATION, RelationRef


@dataclass
class AgreementResult:
    n_items: int
    n_agree: int
    percent_agreement: float
    cohens_kappa: float | None  # None when undefined (fewer than 2 labels observed)
    disagreements: list[tuple[str, str, str]]  # (item_key, label_a, label_b)

    def as_dict(self) -> dict:
        return {
            "n_items": self.n_items,
            "n_agree": self.n_agree,
            "percent_agreement": round(self.percent_agreement, 4),
            "cohens_kappa": round(self.cohens_kappa, 4) if self.cohens_kappa is not None else None,
            "disagreement_examples": [
                {"item": k, "annotator_a": a, "annotator_b": b}
                for k, a, b in self.disagreements[:20]
            ],
        }


def cohens_kappa(pairs: list[tuple[str, str]]) -> float | None:
    """Unweighted Cohen's kappa over a list of (label_a, label_b) judgements.

    ``pairs`` must be aligned: each element is the same item judged by both
    annotators. Returns ``None`` if fewer than two distinct labels appear
    across both annotators (kappa is undefined - there is no chance agreement
    to correct for).
    """
    n = len(pairs)
    if n == 0:
        return None

    labels = sorted({label for pair in pairs for label in pair})
    if len(labels) < 2:
        return None

    observed = sum(1 for a, b in pairs if a == b) / n

    count_a = Counter(a for a, _ in pairs)
    count_b = Counter(b for _, b in pairs)
    expected = sum((count_a[label] / n) * (count_b[label] / n) for label in labels)

    if expected == 1.0:
        return 1.0 if observed == 1.0 else 0.0
    return (observed - expected) / (1 - expected)


def _agree(pred_keys: set, gold_keys: set, key_to_label: dict) -> AgreementResult:
    all_keys = pred_keys | gold_keys
    pairs: list[tuple[str, str]] = []
    disagreements: list[tuple[str, str, str]] = []

    for key in all_keys:
        label_a = key_to_label.get(("a", key), NO_RELATION)
        label_b = key_to_label.get(("b", key), NO_RELATION)
        pairs.append((label_a, label_b))
        if label_a != label_b:
            disagreements.append((str(key), label_a, label_b))

    n_agree = len(pairs) - len(disagreements)
    return AgreementResult(
        n_items=len(pairs),
        n_agree=n_agree,
        percent_agreement=n_agree / len(pairs) if pairs else 0.0,
        cohens_kappa=cohens_kappa(pairs),
        disagreements=disagreements,
    )


def entity_agreement(
    annotation_a: list[EntityRef], annotation_b: list[EntityRef], criterion: str = "normalised"
) -> AgreementResult:
    """Agreement on *which entities were extracted*, presence/absence per (turn, entity).

    Type is folded into the key only for ``criterion="typed"`` (same convention
    as `entity_prf`), so a plain presence/absence disagreement is distinguished
    from a "found it, disagreed on type" disagreement.
    """

    def key_of(ref: EntityRef) -> tuple:
        if criterion == "typed":
            return (ref.turn_id, normalise(ref.name), ref.type)
        return (ref.turn_id, normalise(ref.name))

    keys_a = {key_of(r) for r in annotation_a}
    keys_b = {key_of(r) for r in annotation_b}
    key_to_label = {("a", k): "present" for k in keys_a} | {("b", k): "present" for k in keys_b}
    return _agree(keys_a, keys_b, key_to_label)


def relation_agreement(
    annotation_a: list[RelationRef], annotation_b: list[RelationRef]
) -> AgreementResult:
    """Agreement on the label assigned to each (source, target) pair.

    A pair one annotator omitted is treated as ``no_relation`` from them - the
    same convention `relation_accuracy.confusion_matrix` uses for
    prediction-vs-gold, applied here to annotator-vs-annotator.
    """
    map_a = {(r.source, r.target): r.relation for r in annotation_a}
    map_b = {(r.source, r.target): r.relation for r in annotation_b}
    all_pairs = set(map_a) | set(map_b)
    key_to_label = {("a", p): map_a.get(p, NO_RELATION) for p in all_pairs} | {
        ("b", p): map_b.get(p, NO_RELATION) for p in all_pairs
    }
    return _agree(set(map_a), set(map_b), key_to_label)


def subcase_vs_depends_on_agreement(
    annotation_a: list[RelationRef], annotation_b: list[RelationRef]
) -> AgreementResult:
    """The specific check the stats report asked for.

    Restricts to pairs where *either* annotator said ``subcase`` or
    ``depends_on`` (the two labels found to co-occur suspiciously often),
    ignoring every other label pair entirely - this measures whether a second
    annotator draws the same subcase/depends_on line, not general relation
    agreement, which `relation_agreement` already covers.
    """
    watched = {"subcase", "depends_on"}
    filt_a = [r for r in annotation_a if r.relation in watched]
    filt_b = [r for r in annotation_b if r.relation in watched]
    map_a = {(r.source, r.target): r.relation for r in filt_a}
    map_b = {(r.source, r.target): r.relation for r in filt_b}
    all_pairs = {p for p in (set(map_a) | set(map_b))}
    key_to_label = {("a", p): map_a.get(p, NO_RELATION) for p in all_pairs} | {
        ("b", p): map_b.get(p, NO_RELATION) for p in all_pairs
    }
    return _agree(set(map_a), set(map_b), key_to_label)
