import pytest
from pydantic import ValidationError

from src.model.domain.evaluation import (
    EvaluationResult,
    EvaluationRule,
    NamingUnderstandabilityScore,
    NodeEvaluation,
    RelationEvaluation,
)


def test_evaluation_result_serializes_candidate_element_metrics() -> None:
    result = EvaluationResult(
        node_evaluations=[
            NodeEvaluation(
                id="node-1",
                syntactic_errors=[2],
                rules_applied=[1, 2],
                naming_score=NamingUnderstandabilityScore.HIGH,
            )
        ],
        relation_evaluations=[
            RelationEvaluation(
                id="relation-1",
                syntactic_errors=[],
                rules_applied=[1],
            )
        ],
        applied_rules=[
            EvaluationRule(rule_id=1, content="Actors initiate use cases."),
            EvaluationRule(
                rule_id=2, content="Use case names start with verbs."
            ),
        ],
    )

    assert result.model_dump(mode="json") == {
        "node_evaluations": [
            {
                "id": "node-1",
                "syntactic_errors": [2],
                "rules_applied": [1, 2],
                "naming_score": 3,
            }
        ],
        "relation_evaluations": [
            {
                "id": "relation-1",
                "syntactic_errors": [],
                "rules_applied": [1],
            }
        ],
        "applied_rules": [
            {"rule_id": 1, "content": "Actors initiate use cases."},
            {"rule_id": 2, "content": "Use case names start with verbs."},
        ],
    }


def test_evaluation_result_rejects_positional_rules() -> None:
    with pytest.raises(ValidationError):
        EvaluationResult.model_validate(
            {
                "node_evaluations": [],
                "relation_evaluations": [],
                "applied_rules": [[1, "Actors initiate use cases."]],
            }
        )


def test_node_evaluation_requires_naming_score() -> None:
    with pytest.raises(ValidationError):
        NodeEvaluation.model_validate(
            {
                "id": "node-1",
                "syntactic_errors": [],
                "rules_applied": [],
            }
        )
