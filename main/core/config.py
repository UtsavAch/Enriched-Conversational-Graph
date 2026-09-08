"""Central configuration.

Every number in this file is a knob someone will want to sweep. Putting them all
here - rather than scattering literals through the pipeline - is what makes the
Phase 4 parameter study a config change rather than a code change.

PROVENANCE MATTERS. Each value below is annotated with where it came from:

* ``[thesis]``      - selected empirically in the baseline thesis. Changing it
                      invalidates comparability with the published numbers.
* ``[provisional]`` - a working assumption, explicitly flagged in the Phase 1-2
                      report as unfit / a Phase 4 sweep target. Do not report
                      these as findings.
* ``[engineering]`` - an implementation choice with no research content.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

# --------------------------------------------------------------------------
# Paths
# --------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_ROOT = Path(os.environ.get("GM_DATA_ROOT", PROJECT_ROOT / "data"))
CONVERSATIONS_DIR = DATA_ROOT / "conversations"
DOCUMENTS_DIR = DATA_ROOT / "documents"
EVAL_CORPORA_DIR = DATA_ROOT / "eval_corpora"


# --------------------------------------------------------------------------
# Retrieval / context assembly
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class ContextProfile:
    """A budget allocation for one purpose.

    Two primary profiles exist because assembling context to *answer a question*
    and assembling candidates to *classify an edge* are different jobs with
    different cost tolerances. Five additional named profiles reproduce the
    ablation baselines required by Task 4.4 (section 5.4-5.5).

    Parameters
    ----------
    r_pragmatic:
        Controls the graph-slot budget split between hierarchical and pragmatic
        edge pools. ``None`` (default) = pooled best-edge-wins scoring (the
        ENRICHED production behaviour). A float in [0, 1] = split the G slots,
        giving G*r_pragmatic to pragmatic and the rest to hierarchical.
        Section 5.5, step 4 of the Phase 1-2 report.
    compress:
        When True, historical-layer nodes are rendered at the cheapest tier
        that fits within the remaining token budget (full → summary →
        reference). When False, every node is rendered at full. Section 3.6.
    count_retrieval:
        When True, ``retrieval_count`` is incremented for every node pulled
        into context. False for write-time candidate selection (being selected
        for edge classification is a different event from being retrieved to
        answer a query). Section 5.5, ``bump_retrieval``.
    """

    name: str
    n_recent: int = 5
    k_semantic: int = 5
    k_entity: int = 2
    k_state: int = 2
    graph_slots_fraction: float = 0.25
    k_historical: int = 40
    k_documents: int = 0
    r_pragmatic: float | None = None   # [provisional] None = pooled
    compress: bool = False             # [provisional]
    count_retrieval: bool = False      # [provisional]

    @property
    def graph_slots(self) -> int:
        return int(self.k_historical * self.graph_slots_fraction)


#: Used when generating an answer to the user. [thesis] for k_historical and
#: graph_slots_fraction (chapter 3, table 3.9); [provisional] for the rest,
#: which are new in Phase 1-2 and are Phase 4 sweep targets.
#: Section 5.5 of the Phase 1-2 report.
ANSWER_PROFILE = ContextProfile(
    name="answer",
    n_recent=5,                  # [thesis] LAYER1_RECENT_TURNS
    k_historical=40,             # [thesis] K_HISTORICAL (K_target - N_recent = 45 - 5)
    graph_slots_fraction=0.25,   # [thesis] GRAPH_SLOTS_FRACTION
    k_semantic=5,                # [thesis] K_SEMANTIC (graph entry points)
    k_entity=2,                  # [provisional] sweep 0/2/4
    k_state=2,                   # [provisional] sweep 0/2/4
    k_documents=3,               # [provisional] external RAG slots
    r_pragmatic=None,            # [provisional] None = pooled (ENRICHED default)
    compress=True,               # [provisional] greedy first-fit compression
    count_retrieval=True,        # [provisional] track retrieval_count
)

#: Used when selecting candidate prior nodes for edge classification (W2/W3).
#: Small on purpose: the candidate cap is one of the two mechanisms that keep
#: per-turn cost bounded (thesis section 3.3). Section 5.5, EDGE_PROFILE.
EDGE_PROFILE = ContextProfile(
    name="edge",
    n_recent=1,                  # [provisional] guarantee the immediately prior turn
    k_semantic=3,                # [provisional]
    k_entity=2,                  # [provisional]
    k_state=2,                   # [provisional]
    k_historical=8,              # [provisional] K_target=8, so K_historical=8-1=7 + 1 recent
    graph_slots_fraction=0.5,    # [provisional] half of historical slots from graph
    k_documents=0,
    r_pragmatic=None,            # not applicable at write time
    compress=False,              # candidates are rendered without compression
    count_retrieval=False,       # write-time selection is a different event
)

#: External document chunks get their OWN budget, not a share of the graph
#: slots. This is deliberate: it keeps the thesis' displacement analysis
#: interpretable, because you can always say how many slots went to dialogue
#: memory vs. how many went to external documents. [engineering + provisional]
RAG_SLOTS_ARE_SEPARATE = True


# --------------------------------------------------------------------------
# Task 4.4 comparison profiles
# --------------------------------------------------------------------------
#
# All five conditions are based on ANSWER_PROFILE, changing only the parameters
# being compared. Everything else remains fixed so only retrieval composition
# varies between conditions. Section 5.5 of the Phase 1-2 report.
#
# These reproduce the ablation baselines as degenerate parameter settings of
# assemble_context rather than separate codebases, which removes implementation-
# divergence as a confound.

RECENCY_ONLY_PROFILE = ContextProfile(
    name="recency_only",
    n_recent=45,            # K_target forces K_historical to zero → short-circuit
    k_historical=40,
    graph_slots_fraction=0.25,
    k_semantic=5,
    k_entity=2,
    k_state=2,
    k_documents=3,
    r_pragmatic=None,
    compress=True,
    count_retrieval=True,
)

BASELINE_SEMANTIC_PROFILE = ContextProfile(
    name="baseline_semantic",
    n_recent=5,
    k_historical=40,
    graph_slots_fraction=0.0,  # no graph slots → all historical filled semantically
    k_semantic=5,
    k_entity=0,                # no entity anchoring
    k_state=0,                 # no state-node anchoring
    k_documents=3,
    r_pragmatic=None,          # no effect when graph_slots_fraction=0
    compress=True,
    count_retrieval=True,
)

BASELINE_HIERARCHICAL_PROFILE = ContextProfile(
    name="baseline_hierarchical",
    n_recent=5,
    k_historical=40,
    graph_slots_fraction=0.25,
    k_semantic=5,
    k_entity=0,                # no entity anchoring (Oliveira baseline)
    k_state=0,                 # no state-node anchoring (Oliveira baseline)
    k_documents=3,
    r_pragmatic=0.0,           # 0% of graph slots from pragmatic pool → hierarchical only
    compress=True,
    count_retrieval=True,
)

PRAGMATIC_ONLY_PROFILE = ContextProfile(
    name="pragmatic_only",
    n_recent=5,
    k_historical=40,
    graph_slots_fraction=0.25,
    k_semantic=5,
    k_entity=0,
    k_state=0,
    k_documents=3,
    r_pragmatic=1.0,           # 100% of graph slots from pragmatic pool
    compress=True,
    count_retrieval=True,
)

ENRICHED_PROFILE = ANSWER_PROFILE  # r_pragmatic=None → pooled best-edge-wins


# --------------------------------------------------------------------------
# Edge strengths
# --------------------------------------------------------------------------
#
# [provisional] ALL of these. The Phase 1-2 report is explicit: these encode a
# working assumption by analogy, not a measured quantity. They are the starting
# point for the Phase 4 parameter sweep, not a finding. Do not cite them.

HIERARCHICAL_EDGE_STRENGTH: dict[str, float] = {
    "subcase": 1.0,
    "supercase": 0.8,
    "same_level": 0.6,
}

PRAGMATIC_EDGE_STRENGTH: dict[str, float] = {
    "revises": 1.0,
    "contradicts": 0.9,
    "resolves": 0.85,
    "depends_on": 0.7,
    "references": 0.5,
}

STATE_RELATION_STRENGTH: dict[str, float] = {
    "resolves": 0.85,
    "contradicts": 0.9,
    "constrained_by": 0.7,
    "supports": 0.6,
}


# --------------------------------------------------------------------------
# Pipeline
# --------------------------------------------------------------------------


@dataclass
class PipelineConfig:
    """Which extraction strategy to run, and how hard to try.

    ``strategy`` selects between the two designs the Phase 1-2 report leaves
    open (section 5.2): five task-scoped calls, or one combined call. The report
    says explicitly that this comparison should be "a configuration change, not
    a rewrite" - this field is that seam.
    """

    strategy: str = "multi_call"  # or "combined_call"  [provisional]
    max_retries: int = 2          # [engineering]
    request_timeout_s: float = 60.0  # [engineering]

    #: Best-effort extraction: if an extraction call fails, keep the node and the
    #: parts that succeeded rather than dropping the turn. Inherited from the
    #: baseline architecture (thesis section 3.3). Turning this off is useful in
    #: tests, where you want failures to be loud.
    best_effort: bool = True

    #: Determinism. The thesis fixes a seed and a low temperature for edge
    #: classification so results are reproducible. [thesis]
    extraction_temperature: float = 0.0
    answer_temperature: float = 0.2
    seed: int = 42


@dataclass
class ModelConfig:
    """Model identifiers. Swapping models — including to a local SLM via an
    OpenAI-compatible endpoint — should be a config/environment edit only."""

    answer_model: str = os.environ.get("GM_ANSWER_MODEL", "claude-sonnet-4-6")
    extraction_model: str = os.environ.get("GM_EXTRACTION_MODEL", "claude-sonnet-4-6")
    embedding_model: str = os.environ.get("GM_EMBEDDING_MODEL", "hashing")
    embedding_dim: int = 768  # [thesis] 768-d vectors compared by dot product

    #: Base URL for an OpenAI-compatible endpoint (Ollama, vLLM, etc.).
    #: Set GM_OPENAI_BASE_URL to use a local SLM instead of Anthropic.
    openai_base_url: str | None = os.environ.get("GM_OPENAI_BASE_URL")
    openai_api_key: str = os.environ.get("GM_OPENAI_API_KEY", "ollama")


# --------------------------------------------------------------------------
# RAG (external documents) - kept intentionally simple for now
# --------------------------------------------------------------------------


@dataclass
class RagConfig:
    """Simple fixed-size chunking + cosine top-k. Nothing clever, on purpose.

    This is a *baseline* document retriever, not a contribution. Anything
    fancier (semantic chunking, reranking, hybrid BM25) should be added only if
    validation shows the simple version is the bottleneck - and should then be
    evaluated as a change, against this baseline.
    """

    chunk_size_chars: int = 1200   # [engineering] ~250-300 tokens
    chunk_overlap_chars: int = 200  # [engineering]
    min_chunk_chars: int = 100     # [engineering] drop fragments smaller than this
    top_k: int = 3                 # [provisional]
    min_similarity: float = 0.0    # [provisional] 0.0 = no floor, return top-k always


@dataclass
class Settings:
    """The one object the rest of the codebase reads configuration from."""

    pipeline: PipelineConfig = field(default_factory=PipelineConfig)
    models: ModelConfig = field(default_factory=ModelConfig)
    rag: RagConfig = field(default_factory=RagConfig)
    answer_profile: ContextProfile = ANSWER_PROFILE
    edge_profile: ContextProfile = EDGE_PROFILE
    data_root: Path = DATA_ROOT


#: Module-level default. Tests and experiments should construct their own
#: ``Settings`` rather than mutating this one.
settings = Settings()
