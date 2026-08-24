from enum import IntEnum
from typing import NamedTuple

from pydantic import BaseModel, Field


class NamingUnderstandabilityScore(IntEnum):
    """Element name clarity score."""

    LOW = 1
    MEDIUM = 2
    HIGH = 3


class EvaluationRule(NamedTuple):
    rule_id: int
    content: str


class BaseEvaluation(BaseModel):
    """Candidate element evaluation."""

    id: str = Field(description="Candidate element ID.")
    syntactic_errors: list[int] = Field(description="Violated rule IDs.")
    rules_applied: list[int] = Field(description="Applied rule IDs.")

    def is_eval_valid(self, catalog_rule_ids: set[int]) -> bool:
        applied_rules_are_unique = len(self.rules_applied) == len(
            set(self.rules_applied)
        )
        syntactic_errors_are_unique = len(self.syntactic_errors) == len(
            set(self.syntactic_errors)
        )
        errors_are_applied = set(self.syntactic_errors) <= set(
            self.rules_applied
        )
        applied_rules_are_cataloged = (
            set(self.rules_applied) <= catalog_rule_ids
        )
        return (
            applied_rules_are_unique
            and syntactic_errors_are_unique
            and errors_are_applied
            and applied_rules_are_cataloged
        )


class NodeEvaluation(BaseEvaluation):
    naming_score: NamingUnderstandabilityScore = Field(
        description=(
            "Naming clarity: 1 unclear; 2 clear, protocol-violating; 3 clear, "
            "protocol-compliant."
        )
    )
    combined_initiator_effect: int = Field(
        description="Relations targeting node."
    )
    combined_target_effect: int = Field(
        description="Relations originating from node."
    )


class RelationEvaluation(BaseEvaluation):
    """Candidate relation evaluation."""

    ...


class EvaluationResult(BaseModel):
    """Candidate diagram evaluation result."""

    node_evaluations: list[NodeEvaluation] = Field(
        description="Evaluated candidate nodes."
    )
    relation_evaluations: list[RelationEvaluation]
    applied_rules: list[EvaluationRule] = Field(
        description="Applied rules: [rule_id, rule_text]."
    )
