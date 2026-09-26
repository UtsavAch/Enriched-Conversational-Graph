"""Regression tests for two evaluation bugs.

1. relation_accuracy keyed edges by (source, target), so a pragmatic label on a
   pair overwrote the hierarchical label on the same pair.
2. llm_judge parsed with a bare json.loads, so fenced JSON became verdict "error".
"""

from types import SimpleNamespace

from evaluation.metrics.consistency import ConsistencyProbe
from evaluation.metrics.llm_judge import judge_consistency
from evaluation.metrics.relation_accuracy import (
    RelationRef,
    confusion_matrix,
    per_relation_prf,
    resolution_linking_accuracy,
)


def R(source, target, relation):
    return RelationRef(source=source, target=target, relation=relation)


# --- relation_accuracy -----------------------------------------------------------

def test_both_families_on_one_pair_are_scored():
    gold = [R("N_3", "N_2", "subcase"), R("N_3", "N_2", "resolves")]
    out = per_relation_prf(gold, gold)
    assert out["subcase"]["support"] == 1 and out["subcase"]["f1"] == 1.0
    assert out["resolves"]["support"] == 1 and out["resolves"]["f1"] == 1.0


def test_missing_hierarchical_edge_is_a_miss_not_hidden():
    gold = [R("N_3", "N_2", "subcase"), R("N_3", "N_2", "resolves")]
    pred = [R("N_3", "N_2", "resolves")]
    out = per_relation_prf(pred, gold)
    assert out["subcase"]["recall"] == 0.0
    assert out["resolves"]["f1"] == 1.0
    assert confusion_matrix(pred, gold)["subcase"] == {"no_relation": 1}


def test_labels_do_not_cross_families():
    gold = [R("N_3", "N_2", "resolves")]
    pred = [R("N_3", "N_2", "subcase")]
    m = confusion_matrix(pred, gold)
    assert m["resolves"] == {"no_relation": 1}
    assert m["no_relation"] == {"subcase": 1}


def test_family_filter_and_family_macros():
    gold = [R("N_3", "N_2", "subcase"), R("N_3", "N_2", "resolves"), R("N_4", "N_1", "depends_on")]
    pred = [R("N_3", "N_2", "subcase"), R("N_4", "N_1", "depends_on")]
    assert set(confusion_matrix(pred, gold, family="hierarchical")) == {"subcase"}
    out = per_relation_prf(pred, gold)
    assert out["macro_avg_hierarchical"]["f1"] == 1.0
    assert out["macro_avg_pragmatic"]["support"] == 2  # resolves + depends_on
    assert out["macro_avg_excl_no_relation"]["support"] == 3


def test_resolution_linking_unchanged():
    gold = [R("N_3", "N_2", "subcase"), R("N_3", "N_2", "resolves")]
    assert resolution_linking_accuracy(gold, gold) == {"precision": 1.0, "recall": 1.0, "gold_count": 1}


# --- llm_judge ---------------------------------------------------------------

PROBE = ConsistencyProbe(probe_id="p1", question="q?", target="SN_1", expected_any=["x"])


def _judge(raw):
    client = SimpleNamespace(complete=lambda **kw: SimpleNamespace(text=raw))
    return judge_consistency(client, PROBE, "decision", "answer", model_name="m")


def test_judge_plain_json():
    assert _judge('{"verdict": "consistent", "rationale": "ok"}').verdict == "consistent"


def test_judge_fenced_json():
    v = _judge('```json\n{"verdict": "contradicts", "rationale": "no"}\n```')
    assert v.verdict == "contradicts" and v.rationale == "no"


def test_judge_json_with_preamble():
    assert _judge('Here you go: {"verdict": "unclear", "rationale": "?"}').verdict == "unclear"


def test_judge_garbage_is_error():
    assert _judge("I think it's fine.").verdict == "error"


def test_judge_unknown_verdict_is_error():
    assert _judge('{"verdict": "maybe"}').verdict == "error"
