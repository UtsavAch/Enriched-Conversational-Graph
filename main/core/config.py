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

    Two profiles exist because assembling context to *answer a question* and
    assembling candidates to *classify an edge* are different jobs with
    different cost tolerances.
    """

    name: str
    n_recent: int = 5
    k_semantic: int = 5
    k_entity: int = 3
    k_state: int = 3
    graph_slots_fraction: float = 0.25
    k_historical: int = 40
    k_documents: int = 0

    @property
    def graph_slots(self) -> int:
        return int(self.k_historical * self.graph_slots_fraction)


#: Used when generating an answer to the user. [thesis] for k_historical and
#: graph_slots_fraction (chapter 3, table 3.9); [provisional] for the rest,
#: which are new in Phase 1-2 and are Phase 4 sweep targets.
ANSWER_PROFILE = ContextProfile(
    name="answer",
    n_recent=5,          # [thesis] LAYER1_RECENT_TURNS
    k_historical=40,     # [thesis] K_HISTORICAL
    graph_slots_fraction=0.25,  # [thesis] GRAPH_SLOTS_FRACTION
    k_semantic=5,        # [thesis] K_SEMANTIC (graph entry points)
    k_entity=3,          # [provisional]
    k_state=3,           # [provisional]
    k_documents=3,       # [provisional] external RAG slots, see note below
)

#: Used when selecting candidate prior nodes for edge classification (W2/W3).
#: Small on purpose: the candidate cap is one of the two mechanisms that keep
#: per-turn cost bounded (thesis section 3.3).
EDGE_PROFILE = ContextProfile(
    name="edge",
    n_recent=0,
    k_semantic=8,        # [thesis] K_EDGE_CLASSIFICATION
    k_entity=0,
    k_state=0,
    k_historical=8,
    graph_slots_fraction=0.0,
    k_documents=0,
)

#: External document chunks get their OWN budget, not a share of the graph
#: slots. This is deliberate: it keeps the thesis' displacement analysis
#: interpretable, because you can always say how many slots went to dialogue
#: memory vs. how many went to external documents. [engineering + provisional]
RAG_SLOTS_ARE_SEPARATE = True


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
    "resolves": 0.9,
    "depends_on": 0.8,
    "references": 0.5,
}

STATE_RELATION_STRENGTH: dict[str, float] = {
    "resolves": 1.0,
    "contradicts": 0.9,
    "constrained_by": 0.8,
    "supports": 0.7,
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
    """Model identifiers. Swapping models should be a config edit only."""

    answer_model: str = os.environ.get("GM_ANSWER_MODEL", "claude-sonnet-4-6")
    extraction_model: str = os.environ.get("GM_EXTRACTION_MODEL", "claude-sonnet-4-6")
    embedding_model: str = os.environ.get("GM_EMBEDDING_MODEL", "hashing")
    embedding_dim: int = 768  # [thesis] 768-d vectors compared by dot product


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
