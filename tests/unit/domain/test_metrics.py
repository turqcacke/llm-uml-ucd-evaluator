from decimal import Decimal

import pytest

from src.model.domain.diagram_presentation import UseCaseDiagramPresentation
from src.model.domain.evaluation import (
    ElementSyntacticEvaluation,
    EvaluationResult,
    NamingUnderstandabilityScore,
    NodeNamingEvaluation,
    PragmaticEvaluationResult,
    SyntacticEvaluationResult,
)
from src.model.domain.matching import (
    ExtendedMatching,
    NodeMatch,
    RelationMatch,
)
from src.model.domain.metrics import Metrics
from src.model.domain.node import Node, NodeType
from src.model.domain.relation import NodeRelation, NodeRelationType


def _evaluation_for(candidate: UseCaseDiagramPresentation) -> EvaluationResult:
    return EvaluationResult(
        syntactic=SyntacticEvaluationResult(
            nodes=[
                ElementSyntacticEvaluation(uid=node.uid, checks={})
                for node in candidate.nodes
                if node.type not in {NodeType.NOTE, NodeType.OTHER}
            ],
            relations=[
                ElementSyntacticEvaluation(uid=relation.uid, checks={})
                for relation in candidate.relations
            ],
        ),
        pragmatic=PragmaticEvaluationResult(
            nodes=[
                NodeNamingEvaluation(
                    uid=node.uid, score=NamingUnderstandabilityScore.MEDIUM
                )
                for node in candidate.nodes
                if node.type in {NodeType.ACTOR, NodeType.USECASE}
            ]
        ),
    )


def _diagram_with_relations(
    *relation_types: NodeRelationType,
) -> UseCaseDiagramPresentation:
    return UseCaseDiagramPresentation(
        nodes=[
            Node(uid="actor", name="Actor", type=NodeType.ACTOR),
            Node(uid="usecase", name="Use case", type=NodeType.USECASE),
        ],
        relations=[
            NodeRelation(
                uid=str(index),
                source="actor",
                target="usecase",
                type=relation_type,
            )
            for index, relation_type in enumerate(relation_types)
        ],
    )


def _calculate_unmatched(
    candidate: UseCaseDiagramPresentation,
    evaluation: EvaluationResult,
) -> Metrics:
    reference = UseCaseDiagramPresentation(
        nodes=[Node(uid="reference", name="Reference", type=NodeType.ACTOR)],
        relations=[],
    )
    return Metrics.calculate_metrics(
        reference,
        candidate,
        evaluation,
        ExtendedMatching(
            reference=reference,
            candidate=candidate,
            node_matches=[],
            relation_matches=[],
        ),
    )


def test_metrics_consume_separated_evaluation_properties():
    candidate = _diagram_with_relations(NodeRelationType.ASSOCIATION)
    evaluation = EvaluationResult(
        syntactic=SyntacticEvaluationResult(
            nodes=[
                ElementSyntacticEvaluation(
                    uid="actor",
                    checks={"name_present": False, "parent_exists": False},
                ),
                ElementSyntacticEvaluation(
                    uid="usecase",
                    checks={"name_present": True, "parent_exists": True},
                ),
            ],
            relations=[ElementSyntacticEvaluation(uid="0", checks={})],
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
    result = _calculate_unmatched(candidate, evaluation)
    assert result.syntactic_error_rate == Decimal("0.5")
    assert result.naming_understandability_score == Decimal(2)


def test_allowed_candidate_without_checks_has_zero_syntactic_error_rate():
    candidate = _diagram_with_relations()
    result = _calculate_unmatched(candidate, _evaluation_for(candidate))
    assert result.syntactic_error_rate == Decimal(0)


def test_semantic_metrics_count_nodes_and_relations_without_annotations() -> (
    None
):
    reference = UseCaseDiagramPresentation(
        nodes=[
            Node(uid=kind.value, name=kind.value, type=kind)
            for kind in NodeType
        ],
        relations=[
            NodeRelation(
                uid=kind.value, source="actor", target="usecase", type=kind
            )
            for kind in NodeRelationType
        ],
    )
    candidate = UseCaseDiagramPresentation(
        nodes=reference.nodes
        + [Node(uid="extra", name="Extra", type=NodeType.ACTOR)],
        relations=reference.relations
        + [
            NodeRelation(
                uid="extra",
                source="extra",
                target="usecase",
                type=NodeRelationType.ASSOCIATION,
            )
        ],
    )
    matching = ExtendedMatching(
        reference=reference,
        candidate=candidate,
        node_matches=[
            NodeMatch(reference_uid=kind.value, candidate_uid=kind.value)
            for kind in (
                NodeType.ACTOR,
                NodeType.SYSTEM_BOUNDARY,
                NodeType.NOTE,
                NodeType.OTHER,
            )
        ],
        relation_matches=[
            RelationMatch(reference_uid=kind.value, candidate_uid=kind.value)
            for kind in (
                NodeRelationType.INCLUDE,
                NodeRelationType.GENERALIZATION,
            )
        ],
    )

    result = Metrics.calculate_metrics(
        reference,
        candidate,
        _evaluation_for(candidate),
        matching,
    )

    assert result.candidate_is_allowed is True
    assert result.completeness_rate == Decimal(4) / Decimal(7)
    assert result.redundancy_rate == Decimal(5) / Decimal(9)
    assert result.semantic_precision == Decimal(4) / Decimal(9)
    assert result.semantic_f1_score == Decimal("0.5")
    assert all(
        isinstance(value, Decimal)
        for name, value in result.model_dump().items()
        if name != "candidate_is_allowed"
    )
    assert "redudancy_rate" not in result.model_dump()
    assert "syntatic_error_rate" not in result.model_dump()


def test_semantic_f1_avoids_intermediate_decimal_rounding() -> None:
    reference = UseCaseDiagramPresentation(
        nodes=[
            Node(uid=f"reference-{index}", name="Actor", type=NodeType.ACTOR)
            for index in range(17)
        ],
        relations=[],
    )
    candidate = UseCaseDiagramPresentation(
        nodes=[
            Node(uid=f"candidate-{index}", name="Actor", type=NodeType.ACTOR)
            for index in range(11)
        ],
        relations=[],
    )
    result = Metrics.calculate_metrics(
        reference,
        candidate,
        _evaluation_for(candidate),
        ExtendedMatching(
            reference=reference,
            candidate=candidate,
            node_matches=[
                NodeMatch(
                    reference_uid=f"reference-{index}",
                    candidate_uid=f"candidate-{index}",
                )
                for index in range(7)
            ],
            relation_matches=[],
        ),
    )

    assert result.semantic_f1_score == Decimal("0.5")
    assert result.model_dump(mode="json") == {
        "candidate_is_allowed": True,
        "redundancy_rate": 0.363636,
        "completeness_rate": 0.411765,
        "semantic_precision": 0.636364,
        "semantic_f1_score": 0.5,
        "syntactic_error_rate": 0,
        "naming_understandability_score": 2,
        "reference_complexity": 0,
        "candidate_complexity": 0,
        "complexity_difference": 0,
        "complexity_deviation_rate": 0,
    }


@pytest.mark.parametrize("matched", [True, False])
def test_semantic_metrics_for_perfect_or_zero_matches(matched: bool) -> None:
    diagram = UseCaseDiagramPresentation(
        nodes=[Node(uid="actor", name="Actor", type=NodeType.ACTOR)],
        relations=[],
    )
    result = Metrics.calculate_metrics(
        diagram,
        diagram,
        _evaluation_for(diagram),
        ExtendedMatching(
            reference=diagram,
            candidate=diagram,
            node_matches=[
                NodeMatch(reference_uid="actor", candidate_uid="actor")
            ]
            if matched
            else [],
            relation_matches=[],
        ),
    )
    assert result.completeness_rate == Decimal(1 if matched else 0)
    assert result.semantic_precision == Decimal(1 if matched else 0)
    assert result.semantic_f1_score == Decimal(1 if matched else 0)
    assert result.redundancy_rate == Decimal(0 if matched else 1)


@pytest.mark.parametrize(
    "node_type",
    [None, NodeType.SYSTEM_BOUNDARY, NodeType.NOTE, NodeType.OTHER],
)
def test_disallowed_candidate_receives_worst_scores(
    node_type: NodeType | None,
) -> None:
    reference = UseCaseDiagramPresentation(
        nodes=[Node(uid="actor", name="Actor", type=NodeType.ACTOR)],
        relations=[],
    )
    candidate = UseCaseDiagramPresentation(
        nodes=[Node(uid="element", name="Element", type=node_type)]
        if node_type
        else [],
        relations=[
            NodeRelation(
                uid="relation",
                source="element",
                target="element",
                type=NodeRelationType.ASSOCIATION,
            )
        ],
    )
    result = Metrics.calculate_metrics(
        reference,
        candidate,
        EvaluationResult(
            syntactic=SyntacticEvaluationResult(nodes=[], relations=[]),
            pragmatic=PragmaticEvaluationResult(nodes=[]),
        ),
        ExtendedMatching(
            reference=reference,
            candidate=candidate,
            node_matches=[],
            relation_matches=[],
        ),
    )
    assert result.candidate_is_allowed is False
    assert result.completeness_rate == Decimal(0)
    assert result.naming_understandability_score == Decimal(0)
    assert result.semantic_precision == Decimal(0)
    assert result.semantic_f1_score == Decimal(0)
    assert result.redundancy_rate == Decimal(1)
    assert result.syntactic_error_rate == Decimal(1)
    assert result.reference_complexity == Decimal(0)
    assert result.candidate_complexity == Decimal(6)
    assert result.complexity_difference == Decimal(6)
    assert result.complexity_deviation_rate == Decimal("Infinity")


@pytest.mark.parametrize("candidate_allowed", [True, False])
@pytest.mark.parametrize(
    "node_type",
    [None, NodeType.SYSTEM_BOUNDARY, NodeType.NOTE, NodeType.OTHER],
)
def test_disallowed_reference_raises_domain_error(
    node_type: NodeType | None, candidate_allowed: bool
) -> None:
    from src.model.domain.exceptions import MetricsCalculationError

    reference = UseCaseDiagramPresentation(
        nodes=[Node(uid="element", name="Element", type=node_type)]
        if node_type
        else [],
        relations=[],
    )
    candidate = UseCaseDiagramPresentation(
        nodes=[Node(uid="actor", name="Actor", type=NodeType.ACTOR)]
        if candidate_allowed
        else [],
        relations=[],
    )
    with pytest.raises(MetricsCalculationError, match="Reference diagram"):
        Metrics.calculate_metrics(
            reference,
            candidate,
            EvaluationResult(
                syntactic=SyntacticEvaluationResult(nodes=[], relations=[]),
                pragmatic=PragmaticEvaluationResult(nodes=[]),
            ),
            ExtendedMatching(
                reference=reference,
                candidate=candidate,
                node_matches=[],
                relation_matches=[],
            ),
        )


@pytest.mark.parametrize(
    ("relation_type", "expected_complexity"),
    [
        (NodeRelationType.ASSOCIATION, Decimal(6)),
        (NodeRelationType.INCLUDE, Decimal(4)),
        (NodeRelationType.EXTEND, Decimal(2)),
        (NodeRelationType.GENERALIZATION, Decimal(0)),
    ],
)
def test_complexity_uses_unit_scenario_relation_weights(
    relation_type: NodeRelationType, expected_complexity: Decimal
) -> None:
    diagram = _diagram_with_relations(relation_type)

    result = Metrics.calculate_metrics(
        diagram,
        diagram,
        _evaluation_for(diagram),
        ExtendedMatching(
            reference=diagram,
            candidate=diagram,
            node_matches=[],
            relation_matches=[],
        ),
    )

    assert result.reference_complexity == expected_complexity
    assert result.candidate_complexity == expected_complexity


@pytest.mark.parametrize(
    ("reference_type", "candidate_type", "difference", "deviation"),
    [
        (
            NodeRelationType.ASSOCIATION,
            NodeRelationType.EXTEND,
            Decimal(-4),
            Decimal(2) / Decimal(3),
        ),
        (
            NodeRelationType.EXTEND,
            NodeRelationType.ASSOCIATION,
            Decimal(4),
            Decimal(2),
        ),
    ],
)
def test_complexity_difference_is_signed_and_deviation_is_absolute(
    reference_type: NodeRelationType,
    candidate_type: NodeRelationType,
    difference: Decimal,
    deviation: Decimal,
) -> None:
    reference = _diagram_with_relations(reference_type)
    candidate = _diagram_with_relations(candidate_type)

    result = Metrics.calculate_metrics(
        reference,
        candidate,
        _evaluation_for(candidate),
        ExtendedMatching(
            reference=reference,
            candidate=candidate,
            node_matches=[],
            relation_matches=[],
        ),
    )

    assert result.complexity_difference == difference
    assert result.complexity_deviation_rate == deviation


def test_equal_zero_complexities_have_zero_deviation() -> None:
    diagram = _diagram_with_relations(NodeRelationType.GENERALIZATION)

    result = Metrics.calculate_metrics(
        diagram,
        diagram,
        _evaluation_for(diagram),
        ExtendedMatching(
            reference=diagram,
            candidate=diagram,
            node_matches=[],
            relation_matches=[],
        ),
    )

    assert result.complexity_difference == Decimal(0)
    assert result.complexity_deviation_rate == Decimal(0)


def test_positive_complexity_against_zero_reference_has_infinite_deviation() -> (
    None
):
    reference = _diagram_with_relations()
    candidate = _diagram_with_relations(NodeRelationType.ASSOCIATION)

    result = Metrics.calculate_metrics(
        reference,
        candidate,
        _evaluation_for(candidate),
        ExtendedMatching(
            reference=reference,
            candidate=candidate,
            node_matches=[],
            relation_matches=[],
        ),
    )

    assert result.complexity_difference == Decimal(6)
    assert result.complexity_deviation_rate == Decimal("Infinity")
    assert result.model_dump(mode="json")["complexity_deviation_rate"] == (
        "Infinity"
    )
