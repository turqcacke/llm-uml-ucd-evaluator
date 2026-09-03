from decimal import ROUND_HALF_EVEN, Decimal
from typing import Self

from pydantic import BaseModel, Field, field_serializer

from .diagram_presentation import UseCaseDiagramPresentation
from .evaluation import EvaluationResult
from .exceptions import MetricsCalculationError
from .matching import ExtendedMatching
from .node import NodeType
from .relation import NodeRelationType


class Metrics(BaseModel):
    candidate_is_allowed: bool
    redundancy_rate: Decimal
    completeness_rate: Decimal
    semantic_precision: Decimal
    semantic_f1_score: Decimal

    syntactic_error_rate: Decimal
    naming_understandability_score: Decimal

    reference_complexity: Decimal
    candidate_complexity: Decimal
    complexity_difference: Decimal
    complexity_deviation_rate: Decimal = Field(allow_inf_nan=True)

    @field_serializer(
        "redundancy_rate",
        "completeness_rate",
        "semantic_precision",
        "semantic_f1_score",
        "syntactic_error_rate",
        "naming_understandability_score",
        "reference_complexity",
        "candidate_complexity",
        "complexity_difference",
        "complexity_deviation_rate",
        when_used="json",
    )
    def serialize_metric(self, value: Decimal) -> int | float | str:
        if not value.is_finite():
            return str(value)
        rounded = value.quantize(Decimal("0.000001"), rounding=ROUND_HALF_EVEN)
        if rounded == rounded.to_integral():
            return int(rounded)
        return float(rounded)

    @classmethod
    def calculate_metrics(
        cls,
        reference: UseCaseDiagramPresentation,
        candidate: UseCaseDiagramPresentation,
        evaluation: EvaluationResult,
        matching: ExtendedMatching,
    ) -> Self:
        if not reference.is_allowed:
            raise MetricsCalculationError("Reference diagram is not allowed.")
        relation_weights = {
            NodeRelationType.ASSOCIATION: 3,
            NodeRelationType.INCLUDE: 2,
            NodeRelationType.EXTEND: 1,
            NodeRelationType.GENERALIZATION: 0,
        }

        def complexity(diagram: UseCaseDiagramPresentation) -> Decimal:
            return Decimal(
                2
                * sum(
                    relation_weights[relation.type]
                    for relation in diagram.relations
                )
            )

        reference_complexity = complexity(reference)
        candidate_complexity = complexity(candidate)
        complexity_difference = candidate_complexity - reference_complexity

        complexity_deviation_rate = Decimal(0)
        if reference_complexity:
            complexity_deviation_rate = (
                abs(complexity_difference) / reference_complexity
            )
        elif candidate_complexity:
            complexity_deviation_rate = Decimal("Infinity")

        if not candidate.is_allowed:
            return cls(
                candidate_is_allowed=False,
                completeness_rate=Decimal(0),
                naming_understandability_score=Decimal(0),
                semantic_precision=Decimal(0),
                semantic_f1_score=Decimal(0),
                redundancy_rate=Decimal(1),
                syntactic_error_rate=Decimal(1),
                reference_complexity=reference_complexity,
                candidate_complexity=candidate_complexity,
                complexity_difference=complexity_difference,
                complexity_deviation_rate=complexity_deviation_rate,
            )
        matched = Decimal(
            len(matching.node_matches) + len(matching.relation_matches)
        )
        reference_count = sum(
            node.type not in {NodeType.NOTE, NodeType.OTHER}
            for node in reference.nodes
        ) + len(reference.relations)
        candidate_count = sum(
            node.type not in {NodeType.NOTE, NodeType.OTHER}
            for node in candidate.nodes
        ) + len(candidate.relations)
        completeness = matched / reference_count
        precision = matched / candidate_count
        redundancy = (
            Decimal(
                len(matching.redundant_nodes)
                + len(matching.redundant_relations)
            )
            / candidate_count
        )
        return cls(
            candidate_is_allowed=candidate.is_allowed,
            completeness_rate=completeness,
            redundancy_rate=redundancy,
            semantic_precision=precision,
            semantic_f1_score=(
                2 * matched / (reference_count + candidate_count)
                if matched
                else Decimal(0)
            ),
            syntactic_error_rate=evaluation.syntactic_error_rate,
            naming_understandability_score=evaluation.naming_understandability_score,
            reference_complexity=reference_complexity,
            candidate_complexity=candidate_complexity,
            complexity_difference=complexity_difference,
            complexity_deviation_rate=complexity_deviation_rate,
        )


class MetricsWithEvaluation(Metrics):
    uid: str
    reference_uid: str
    candidate_uid: str
    reference: UseCaseDiagramPresentation | None = Field(
        default=None, exclude=True
    )
    evaluation: EvaluationResult | None = None
    matching: ExtendedMatching | None = None
