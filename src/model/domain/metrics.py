from collections import Counter
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

    syntactic_error_rate: Decimal
    naming_understandability_score: Decimal

    # Calculations supplied by the subsequent complexity ticket.
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
        included_node_ids = {
            node.id
            for node in candidate.nodes
            if node.type not in {NodeType.NOTE, NodeType.OTHER}
        }
        candidate_node_ids = {node.id for node in candidate.nodes}
        node_evaluation_counts = Counter(
            element.id for element in evaluation.node_evaluations
        )
        relation_evaluation_counts = Counter(
            element.id for element in evaluation.relation_evaluations
        )
        evaluated_node_ids = node_evaluation_counts.keys()
        missing_node_evaluations = not included_node_ids <= evaluated_node_ids
        unknown_node_evaluations = not evaluated_node_ids <= candidate_node_ids
        repeated_node_evaluations = any(
            count != 1 for count in node_evaluation_counts.values()
        )
        invalid_relation_evaluations = relation_evaluation_counts != Counter(
            relation.id for relation in candidate.relations
        )
        if (
            missing_node_evaluations
            or unknown_node_evaluations
            or repeated_node_evaluations
            or invalid_relation_evaluations
        ):
            raise MetricsCalculationError(
                "Candidate elements must each have exactly one evaluation."
            )
        catalog_rule_ids = [rule.rule_id for rule in evaluation.applied_rules]
        catalog_rule_id_set = set(catalog_rule_ids)
        all_evaluations = (
            evaluation.node_evaluations + evaluation.relation_evaluations
        )
        catalog_rule_ids_are_unique = len(catalog_rule_ids) == len(
            catalog_rule_id_set
        )
        evaluations_are_valid = True
        for element in all_evaluations:
            if not element.is_eval_valid(catalog_rule_id_set):
                evaluations_are_valid = False
                break
        if not catalog_rule_ids_are_unique or not evaluations_are_valid:
            raise MetricsCalculationError(
                "Evaluation rule references must be unique and consistent."
            )
        naming_node_ids = {
            node.id
            for node in candidate.nodes
            if node.type
            in {NodeType.ACTOR, NodeType.EXTERNAL_SYSTEM, NodeType.USECASE}
        }
        element_evaluations = [
            element
            for element in evaluation.node_evaluations
            if element.id in included_node_ids
        ] + evaluation.relation_evaluations
        applied_rule_count = sum(
            len(element.rules_applied) for element in element_evaluations
        )
        syntactic_error_count = sum(
            len(element.syntactic_errors) for element in element_evaluations
        )
        naming_scores = [
            element.naming_score
            for element in evaluation.node_evaluations
            if element.id in naming_node_ids
        ]
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
            syntactic_error_rate=(
                Decimal(syntactic_error_count)
                / max(1, applied_rule_count)
            ),
            naming_understandability_score=(
                Decimal(sum(naming_scores)) / len(naming_scores)
            ),
        )
