from decimal import Decimal

import pytest

from src.model.domain.diagram_presentation import UseCaseDiagramPresentation
from src.model.domain.evaluation import EvaluationResult
from src.model.domain.matching import (
    ExtendedMatching,
    NodeMatch,
    RelationMatch,
)
from src.model.domain.metrics import Metrics
from src.model.domain.node import Node, NodeType
from src.model.domain.relation import NodeRelation, NodeRelationType


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
            NodeMatch(kind.value, kind.value)
            for kind in (
                NodeType.ACTOR,
                NodeType.SYSTEM,
                NodeType.NOTE,
                NodeType.OTHER,
            )
        ],
        relation_matches=[
            RelationMatch(kind.value, kind.value)
            for kind in (
                NodeRelationType.INCLUDE,
                NodeRelationType.GENERALIZATION,
            )
        ],
    )

    result = Metrics.calculate_metrics(
        reference,
        candidate,
        EvaluationResult(
            node_evaluations=[], relation_evaluations=[], applied_rules=[]
        ),
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
        if name != "candidate_is_allowed" and value is not None
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
        EvaluationResult(
            node_evaluations=[], relation_evaluations=[], applied_rules=[]
        ),
        ExtendedMatching(
            reference=diagram,
            candidate=diagram,
            node_matches=[NodeMatch("actor", "actor")] if matched else [],
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
        relations=[],
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
