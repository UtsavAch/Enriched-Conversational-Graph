"""Phase 3 / Phase 4 metrics.

Each module measures one thing and says plainly what it does not measure.
Nothing here imports the pipeline: metrics take predictions and gold data as
plain dataclasses, so they can be run over output from any source - including
hand-annotated spreadsheets during early Phase 3 validation.
"""

from evaluation.metrics.consistency import (
    ConsistencyProbe,
    ProbeOutcome,
    aggregate,
    score_keyword_probe,
)
from evaluation.metrics.entity_prf import EntityRef, entity_prf, error_examples
from evaluation.metrics.interannotator import (
    AgreementResult,
    cohens_kappa,
    entity_agreement,
    relation_agreement,
    subcase_vs_depends_on_agreement,
)
from evaluation.metrics.llm_judge import JudgeVerdict, judge_consistency, should_judge
from evaluation.metrics.relation_accuracy import (
    RelationRef,
    confusion_matrix,
    per_relation_prf,
    resolution_linking_accuracy,
)
from evaluation.metrics.state_node_merge import (
    StateNodeRef,
    evaluate_state_nodes,
    token_jaccard,
)

__all__ = [
    "AgreementResult",
    "ConsistencyProbe",
    "EntityRef",
    "ProbeOutcome",
    "RelationRef",
    "StateNodeRef",
    "aggregate",
    "cohens_kappa",
    "confusion_matrix",
    "entity_agreement",
    "entity_prf",
    "error_examples",
    "evaluate_state_nodes",
    "judge_consistency",
    "JudgeVerdict",
    "per_relation_prf",
    "relation_agreement",
    "resolution_linking_accuracy",
    "score_keyword_probe",
    "should_judge",
    "subcase_vs_depends_on_agreement",
    "token_jaccard",
]
