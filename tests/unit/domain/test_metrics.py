from decimal import Decimal

import pytest

from src.model.domain.diagram_presentation import UseCaseDiagramPresentation
from src.model.domain.evaluation import (
    EvaluationResult,
    EvaluationRule,
    NamingUnderstandabilityScore,
    NodeEvaluation,
    RelationEvaluation,
)
from src.model.domain.matching import (
    ExtendedMatching,
    NodeMatch,
    RelationMatch,
)
from src.model.domain.metrics import Metrics
from src.model.domain.node import Node, NodeType
from src.model.domain.relation import NodeRelation, NodeRelationType


def _evaluation_for(
    candidate: UseCaseDiagramPresentation,
) -> EvaluationResult:
    return EvaluationResult(
        node_evaluations=[
            _node_evaluation(node.id)
            for node in candidate.nodes
            if node.type not in {NodeType.NOTE, NodeType.OTHER}
        ],
        relation_evaluations=[
            _relation_evaluation(relation.id)
            for relation in candidate.relations
        ],
        applied_rules=[],
    )


def _node_evaluation(
    element_id: str,
    *,
    syntactic_errors: list[int] | None = None,
    rules_applied: list[int] | None = None,
    naming_score: NamingUnderstandabilityScore = (
        NamingUnderstandabilityScore.MEDIUM
    ),
) -> NodeEvaluation:
    return NodeEvaluation(
        id=element_id,
        syntactic_errors=syntactic_errors or [],
        rules_applied=rules_applied or [],
        naming_score=naming_score,
    )


def _relation_evaluation(element_id: str) -> RelationEvaluation:
    return RelationEvaluation(
        id=element_id, syntactic_errors=[], rules_applied=[]
    )


def _diagram_with_relations(
    *relation_types: NodeRelationType,
) -> UseCaseDiagramPresentation:
    return UseCaseDiagramPresentation(
        nodes=[
            Node(id="actor", name="Actor", type=NodeType.ACTOR),
            Node(id="usecase", name="Use case", type=NodeType.USECASE),
        ],
        relations=[
            NodeRelation(
                id=str(index),
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
        nodes=[Node(id="reference", name="Reference", type=NodeType.ACTOR)],
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


def test_syntactic_and_naming_metrics_aggregate_candidate_evaluations() -> None:
    diagram = UseCaseDiagramPresentation(
        nodes=[
            Node(id="actor", name="Customer", type=NodeType.ACTOR),
            Node(id="usecase", name="Place order", type=NodeType.USECASE),
        ],
        relations=[
            NodeRelation(
                id="relation",
                source="actor",
                target="usecase",
                type=NodeRelationType.ASSOCIATION,
            )
        ],
    )
    evaluation = EvaluationResult(
        node_evaluations=[
            NodeEvaluation(
                id="actor",
                syntactic_errors=[2],
                rules_applied=[1, 2],
                naming_score=NamingUnderstandabilityScore.HIGH,
            ),
            NodeEvaluation(
                id="usecase",
                syntactic_errors=[],
                rules_applied=[1],
                naming_score=NamingUnderstandabilityScore.LOW,
            ),
        ],
        relation_evaluations=[
            RelationEvaluation(
                id="relation", syntactic_errors=[1], rules_applied=[1]
            )
        ],
        applied_rules=[
            EvaluationRule(rule_id=1, content="Rule one"),
            EvaluationRule(rule_id=2, content="Rule two"),
        ],
    )

    result = Metrics.calculate_metrics(
        diagram,
        diagram,
        evaluation,
        ExtendedMatching(
            reference=diagram,
            candidate=diagram,
            node_matches=[
                NodeMatch(reference_id="actor", candidate_id="actor"),
                NodeMatch(reference_id="usecase", candidate_id="usecase"),
            ],
            relation_matches=[
                RelationMatch(
                    reference_id="relation", candidate_id="relation"
                )
            ],
        ),
    )

    assert result.syntactic_error_rate == Decimal("0.5")
    assert result.naming_understandability_score == Decimal(2)


@pytest.mark.parametrize(
    ("node_ids", "relation_ids"),
    [
        ([], ["relation"]),
        (["actor"], []),
        (["actor", "actor"], ["relation"]),
        (["actor"], ["relation", "relation"]),
        (["actor", "foreign"], ["relation"]),
        (["actor"], ["relation", "foreign"]),
    ],
)
def test_metrics_reject_incomplete_or_contradictory_element_evaluations(
    node_ids: list[str], relation_ids: list[str]
) -> None:
    from src.model.domain.exceptions import MetricsCalculationError

    candidate = UseCaseDiagramPresentation(
        nodes=[Node(id="actor", name="Actor", type=NodeType.ACTOR)],
        relations=[
            NodeRelation(
                id="relation",
                source="actor",
                target="actor",
                type=NodeRelationType.ASSOCIATION,
            )
        ],
    )

    with pytest.raises(MetricsCalculationError):
        _calculate_unmatched(
            candidate,
            EvaluationResult(
                node_evaluations=[
                    _node_evaluation(element_id) for element_id in node_ids
                ],
                relation_evaluations=[
                    _relation_evaluation(element_id)
                    for element_id in relation_ids
                ],
                applied_rules=[],
            ),
        )


@pytest.mark.parametrize(
    ("rules_applied", "syntactic_errors", "catalog_ids"),
    [
        ([1, 1], [], [1]),
        ([1], [1, 1], [1]),
        ([], [1], [1]),
        ([2], [], [1]),
        ([1], [], [1, 1]),
    ],
)
def test_metrics_reject_inconsistent_rule_references(
    rules_applied: list[int],
    syntactic_errors: list[int],
    catalog_ids: list[int],
) -> None:
    from src.model.domain.exceptions import MetricsCalculationError

    candidate = UseCaseDiagramPresentation(
        nodes=[Node(id="actor", name="Actor", type=NodeType.ACTOR)],
        relations=[],
    )
    evaluation = EvaluationResult(
        node_evaluations=[
            _node_evaluation(
                "actor",
                syntactic_errors=syntactic_errors,
                rules_applied=rules_applied,
            )
        ],
        relation_evaluations=[],
        applied_rules=[
            EvaluationRule(rule_id=rule_id, content="Rule")
            for rule_id in catalog_ids
        ],
    )

    with pytest.raises(MetricsCalculationError):
        _calculate_unmatched(candidate, evaluation)


def test_allowed_candidate_without_rule_checks_has_zero_syntactic_errors() -> (
    None
):
    candidate = UseCaseDiagramPresentation(
        nodes=[Node(id="actor", name="Actor", type=NodeType.ACTOR)],
        relations=[],
    )

    result = _calculate_unmatched(candidate, _evaluation_for(candidate))

    assert result.syntactic_error_rate == Decimal(0)


def test_excluded_nodes_do_not_change_syntactic_or_naming_metrics() -> None:
    candidate = UseCaseDiagramPresentation(
        nodes=[
            Node(id="actor", name="Actor", type=NodeType.ACTOR),
            Node(
                id="external",
                name="External",
                type=NodeType.EXTERNAL_SYSTEM,
            ),
            Node(id="usecase", name="Use case", type=NodeType.USECASE),
            Node(id="system", name="System", type=NodeType.SYSTEM),
            Node(id="note", name="Note", type=NodeType.NOTE),
            Node(id="other", name="Other", type=NodeType.OTHER),
        ],
        relations=[],
    )
    evaluation = EvaluationResult(
        node_evaluations=[
            _node_evaluation(
                "actor",
                rules_applied=[1],
                naming_score=NamingUnderstandabilityScore.LOW,
            ),
            _node_evaluation(
                "external", naming_score=NamingUnderstandabilityScore.HIGH
            ),
            _node_evaluation(
                "usecase", naming_score=NamingUnderstandabilityScore.MEDIUM
            ),
            _node_evaluation(
                "system",
                rules_applied=[1],
                syntactic_errors=[1],
                naming_score=NamingUnderstandabilityScore.HIGH,
            ),
            _node_evaluation(
                "note", rules_applied=[1], syntactic_errors=[1]
            ),
            _node_evaluation(
                "other", rules_applied=[1], syntactic_errors=[1]
            ),
        ],
        relation_evaluations=[],
        applied_rules=[EvaluationRule(rule_id=1, content="Rule")],
    )

    result = _calculate_unmatched(candidate, evaluation)
    result_without_excluded_evaluations = _calculate_unmatched(
        candidate,
        evaluation.model_copy(
            update={"node_evaluations": evaluation.node_evaluations[:4]}
        ),
    )

    assert result == result_without_excluded_evaluations
    assert result.syntactic_error_rate == Decimal("0.5")
    assert result.naming_understandability_score == Decimal(2)


def test_semantic_metrics_count_nodes_and_relations_without_annotations() -> (
    None
):
    reference = UseCaseDiagramPresentation(
        nodes=[
            Node(id=kind.value, name=kind.value, type=kind)
            for kind in NodeType
        ],
        relations=[
            NodeRelation(
                id=kind.value, source="actor", target="usecase", type=kind
            )
            for kind in NodeRelationType
        ],
    )
    candidate = UseCaseDiagramPresentation(
        nodes=reference.nodes
        + [Node(id="extra", name="Extra", type=NodeType.ACTOR)],
        relations=reference.relations
        + [
            NodeRelation(
                id="extra",
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
            NodeMatch(reference_id=kind.value, candidate_id=kind.value)
            for kind in (
                NodeType.ACTOR,
                NodeType.SYSTEM,
                NodeType.NOTE,
                NodeType.OTHER,
            )
        ],
        relation_matches=[
            RelationMatch(reference_id=kind.value, candidate_id=kind.value)
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
    assert result.completeness_rate == Decimal("0.5")
    assert result.redundancy_rate == Decimal("0.6")
    assert result.semantic_precision == Decimal("0.4")
    assert result.semantic_f1_score == Decimal(4) / Decimal(9)
    assert all(
        isinstance(value, Decimal)
        for name, value in result.model_dump().items()
        if name != "candidate_is_allowed"
    )
    assert "redudancy_rate" not in result.model_dump()
    assert "syntatic_error_rate" not in result.model_dump()


@pytest.mark.parametrize("matched", [True, False])
def test_semantic_metrics_for_perfect_or_zero_matches(matched: bool) -> None:
    diagram = UseCaseDiagramPresentation(
        nodes=[Node(id="actor", name="Actor", type=NodeType.ACTOR)],
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
                NodeMatch(reference_id="actor", candidate_id="actor")
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
    "node_type", [None, NodeType.SYSTEM, NodeType.NOTE, NodeType.OTHER]
)
def test_disallowed_candidate_receives_worst_scores(
    node_type: NodeType | None,
) -> None:
    reference = UseCaseDiagramPresentation(
        nodes=[Node(id="actor", name="Actor", type=NodeType.ACTOR)],
        relations=[],
    )
    candidate = UseCaseDiagramPresentation(
        nodes=[Node(id="element", name="Element", type=node_type)]
        if node_type
        else [],
        relations=[
            NodeRelation(
                id="relation",
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
            node_evaluations=[], relation_evaluations=[], applied_rules=[]
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
    "node_type", [None, NodeType.SYSTEM, NodeType.NOTE, NodeType.OTHER]
)
def test_disallowed_reference_raises_domain_error(
    node_type: NodeType | None, candidate_allowed: bool
) -> None:
    from src.model.domain.exceptions import MetricsCalculationError

    reference = UseCaseDiagramPresentation(
        nodes=[Node(id="element", name="Element", type=node_type)]
        if node_type
        else [],
        relations=[],
    )
    candidate = UseCaseDiagramPresentation(
        nodes=[Node(id="actor", name="Actor", type=NodeType.ACTOR)]
        if candidate_allowed
        else [],
        relations=[],
    )
    with pytest.raises(MetricsCalculationError, match="Reference diagram"):
        Metrics.calculate_metrics(
            reference,
            candidate,
            EvaluationResult(
                node_evaluations=[], relation_evaluations=[], applied_rules=[]
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
