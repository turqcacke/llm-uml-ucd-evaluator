from decimal import Decimal
from typing import Self

from pydantic import BaseModel

from .diagram_presentation import UseCaseDiagramPresentation
from .evaluation import EvaluationResult
from .exceptions import MetricsCalculationError
from .matching import ExtendedMatching
from .node import NodeType


class Metrics(BaseModel):
    candidate_is_allowed: bool
    redundancy_rate: Decimal
    completeness_rate: Decimal
    semantic_precision: Decimal
    semantic_f1_score: Decimal

    # Calculations supplied by the subsequent naming/syntax and complexity tickets.
    syntactic_error_rate: Decimal | None = None
    naming_understandability_score: Decimal | None = None
    reference_complexity: Decimal | None = None
    candidate_complexity: Decimal | None = None
    complexity_deviation_rate: Decimal | None = None

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
        if not candidate.is_allowed:
            return cls(
                candidate_is_allowed=False,
                completeness_rate=Decimal(0),
                naming_understandability_score=Decimal(0),
                semantic_precision=Decimal(0),
                semantic_f1_score=Decimal(0),
                redundancy_rate=Decimal(1),
                syntactic_error_rate=Decimal(1),
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
                2 * completeness * precision / (completeness + precision)
                if completeness + precision
                else Decimal(0)
            ),
        )
