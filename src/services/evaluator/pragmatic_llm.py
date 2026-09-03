from collections import Counter
from dataclasses import dataclass

from src.model.domain import NodeType, UseCaseDiagramPresentation
from src.model.domain.evaluation import PragmaticEvaluationResult
from src.services.exceptions import LlmResponseError
from src.services.ports import ChatModel, LLMRoles
from src.services.shared.prompts import PRAGMATIC_EVALUATOR_REQUEST
from src.services.use_case import UseCase, map_use_case_exceptions


@dataclass(frozen=True)
class PragmaticInput:
    use_case_diagram: UseCaseDiagramPresentation
    description: str | None = None


class PragmaticLlmEvaluator(
    UseCase[PragmaticInput, PragmaticEvaluationResult]
):
    def __init__(self, chat_model: ChatModel[PragmaticEvaluationResult]):
        self._chat_model = chat_model

    @map_use_case_exceptions
    async def execute(self, data: PragmaticInput) -> PragmaticEvaluationResult:
        nodes = [
            node
            for node in data.use_case_diagram.nodes
            if node.type
            in {NodeType.ACTOR, NodeType.EXTERNAL_SYSTEM, NodeType.USECASE}
        ]
        result = await self._chat_model.invoke(
            PRAGMATIC_EVALUATOR_REQUEST.format(
                candidate=data.use_case_diagram.model_dump_json(),
                description=data.description or "",
            ),
            LLMRoles.USER,
        )
        if Counter(node.uid for node in result.nodes) != Counter(
            node.uid for node in nodes
        ):
            raise LlmResponseError(
                "Requested nodes must each have exactly one naming score; "
                "foreign node UIDs are not allowed."
            )
        return result
