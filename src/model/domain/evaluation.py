from decimal import Decimal
from enum import IntEnum

from pydantic import BaseModel, Field


class NamingUnderstandabilityScore(IntEnum):
    """Element name clarity score."""

    LOW = 1
    MEDIUM = 2
    HIGH = 3


class NodeNamingEvaluation(BaseModel):
    uid: str = Field(description="Candidate node UID.")
    score: NamingUnderstandabilityScore = Field(
        description="Naming understandability score under the supplied naming protocol."
    )


class PragmaticEvaluationResult(BaseModel):
    nodes: list[NodeNamingEvaluation]


class ElementSyntacticEvaluation(BaseModel):
    uid: str
    checks: dict[str, bool]


class SyntacticEvaluationResult(BaseModel):
    nodes: list[ElementSyntacticEvaluation]
    relations: list[ElementSyntacticEvaluation]


class EvaluationResult(BaseModel):
    """Already scoped syntactic and pragmatic candidate observations."""

    syntactic: SyntacticEvaluationResult
    pragmatic: PragmaticEvaluationResult

    @property
    def syntactic_error_rate(self) -> Decimal:
        checks = [
            passed
            for element in self.syntactic.nodes + self.syntactic.relations
            for passed in element.checks.values()
        ]
        return Decimal(checks.count(False)) / max(1, len(checks))

    @property
    def naming_understandability_score(self) -> Decimal:
        return Decimal(sum(node.score for node in self.pragmatic.nodes)) / max(
            1, len(self.pragmatic.nodes)
        )
