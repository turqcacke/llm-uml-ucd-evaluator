from decimal import Decimal

import pytest
from pydantic import ValidationError

from src.model.domain.evaluation import (
    ElementSyntacticEvaluation,
    EvaluationResult,
    NamingUnderstandabilityScore,
    NodeNamingEvaluation,
    PragmaticEvaluationResult,
    SyntacticEvaluationResult,
)


def test_evaluation_keeps_separate_evidence_and_aggregates_applied_checks():
    result = EvaluationResult(
        syntactic=SyntacticEvaluationResult(
            nodes=[
                ElementSyntacticEvaluation(
                    uid="actor",
                    checks={"name_present": False, "parent_exists": True},
                ),
                ElementSyntacticEvaluation(
                    uid="system", checks={"name_present": True}
                ),
            ],
            relations=[ElementSyntacticEvaluation(uid="actor", checks={})],
        ),
        pragmatic=PragmaticEvaluationResult(
            nodes=[
                NodeNamingEvaluation(
                    uid="actor", score=NamingUnderstandabilityScore.LOW
                ),
                NodeNamingEvaluation(
                    uid="usecase", score=NamingUnderstandabilityScore.HIGH
                ),
            ]
        ),
    )

    assert result.syntactic_error_rate == Decimal(1) / 3
    assert result.naming_understandability_score == Decimal(2)
    assert result.model_dump(mode="json") == {
        "syntactic": {
            "nodes": [
                {
                    "uid": "actor",
                    "checks": {"name_present": False, "parent_exists": True},
                },
                {"uid": "system", "checks": {"name_present": True}},
            ],
            "relations": [{"uid": "actor", "checks": {}}],
        },
        "pragmatic": {
            "nodes": [
                {"uid": "actor", "score": 1},
                {"uid": "usecase", "score": 3},
            ]
        },
    }


def test_empty_evaluation_has_zero_rates():
    result = EvaluationResult(
        syntactic=SyntacticEvaluationResult(nodes=[], relations=[]),
        pragmatic=PragmaticEvaluationResult(nodes=[]),
    )
    assert result.syntactic_error_rate == Decimal(0)
    assert result.naming_understandability_score == Decimal(0)


@pytest.mark.parametrize(
    "data", [{"uid": "actor"}, {"uid": "actor", "score": 4}]
)
def test_naming_evaluation_requires_supported_score(data):
    with pytest.raises(ValidationError):
        NodeNamingEvaluation.model_validate(data)
