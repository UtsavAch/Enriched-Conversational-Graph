"""Cited turns are always offered to W2/W3 as edge candidates."""

from core.config import EDGE_PROFILE
from core.retrieval.candidate_selection import select_edge_candidates
from core.schema import SCHEMA_VERSION
from core.schema.conversation import ConversationGraph, ConversationMeta
from core.schema.interaction import InteractionNode


def _graph(n: int) -> ConversationGraph:
    g = ConversationGraph(meta=ConversationMeta(conversation_id="t", schema_version=SCHEMA_VERSION))
    for i in range(1, n + 1):
        g.interactions[f"N_{i}"] = InteractionNode(
            id=f"N_{i}", conversation_id="t", turn_index=i - 1, question=f"q{i}", answer=f"a{i}"
        )
    return g


def _new(g: ConversationGraph, citations: list[str]) -> InteractionNode:
    n = len(g.interactions)
    return InteractionNode(id=f"N_{n + 1}", conversation_id="t", turn_index=n,
                           question="q", answer="a", citations=citations)


def _pick(cands):
    return {c.node.id: c.reason for c in cands}


def test_cited_turns_added_on_top_of_recency():
    g = _graph(12)
    picked = _pick(select_edge_candidates(g, _new(g, ["N_2", "N_5"]), EDGE_PROFILE))
    assert picked == {"N_11": "recent", "N_12": "recent", "N_2": "cited", "N_5": "cited"}


def test_disabled_restores_previous_behaviour():
    g = _graph(12)
    picked = _pick(select_edge_candidates(g, _new(g, ["N_2", "N_5"]), EDGE_PROFILE, include_cited=0))
    assert picked == {"N_11": "recent", "N_12": "recent"}


def test_cited_turns_are_capped():
    g = _graph(12)
    cites = ["N_1", "N_2", "N_3", "N_4", "N_5", "N_6", "N_7"]
    picked = _pick(select_edge_candidates(g, _new(g, cites), EDGE_PROFILE, include_cited=5))
    assert [k for k, v in picked.items() if v == "cited"] == ["N_1", "N_2", "N_3", "N_4", "N_5"]


def test_already_chosen_or_non_prior_citations_are_not_duplicated_or_added():
    g = _graph(12)
    # N_12 is already a recent candidate; N_40 does not exist before this turn.
    picked = _pick(select_edge_candidates(g, _new(g, ["N_12", "N_40", "N_3"]), EDGE_PROFILE))
    assert picked == {"N_11": "recent", "N_12": "recent", "N_3": "cited"}


def test_candidates_stay_in_turn_order():
    g = _graph(12)
    order = [c.node.id for c in select_edge_candidates(g, _new(g, ["N_9", "N_2"]), EDGE_PROFILE)]
    assert order == ["N_2", "N_9", "N_11", "N_12"]
