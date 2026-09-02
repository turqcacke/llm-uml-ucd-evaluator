from typing import Protocol

from src.model.domain import Node, NodeType, UseCaseDiagramPresentation
from src.model.domain.evaluation import (
    ElementSyntacticEvaluation,
    SyntacticEvaluationResult,
)
from src.services.use_case import UseCase, map_use_case_exceptions


class ValidationRule[T](Protocol):
    rule_id: str

    def __call__(self, data: T) -> bool: ...


class NamePresent(ValidationRule[Node]):
    rule_id = "name_present"

    def __call__(self, data: Node) -> bool:
        return bool(data.name.strip())


class ParentExists(ValidationRule[Node]):
    rule_id = "parent_exists"

    def __init__(self, node_uids: set[str]) -> None:
        self._node_uids = node_uids

    def __call__(self, data: Node) -> bool:
        return data.parent is None or data.parent in self._node_uids


class SyntacticDiagramEvaluator(
    UseCase[UseCaseDiagramPresentation, SyntacticEvaluationResult]
):
    @map_use_case_exceptions
    async def execute(
        self, data: UseCaseDiagramPresentation
    ) -> SyntacticEvaluationResult:
        rules = (
            NamePresent(),
            ParentExists({node.uid for node in data.nodes}),
        )
        return SyntacticEvaluationResult(
            nodes=[
                ElementSyntacticEvaluation(
                    uid=node.uid,
                    checks={rule.rule_id: rule(node) for rule in rules},
                )
                for node in data.nodes
                if node.type not in {NodeType.NOTE, NodeType.OTHER}
            ],
            relations=[
                ElementSyntacticEvaluation(uid=relation.uid, checks={})
                for relation in data.relations
            ],
        )
