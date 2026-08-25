from dataclasses import dataclass

from src.model.domain import EvaluationResult, UseCaseDiagramPresentation
from src.services.llm_client import ChatModel, LLMRoles
from src.services.shared.prompts import PRAGMATIC_SYNTACTIC_EVALUATOR_REQUEST

from ..base import BasePipeline, map_pipeline_exceptions


@dataclass
class PragmaticSyntaticInput(BasePipeline):
    usecase_diagram: UseCaseDiagramPresentation


class PragmaticSyntaticLlmEvaluator(
    BasePipeline[PragmaticSyntaticInput, EvaluationResult]
):
    def __init__(
        self,
        chat_model: ChatModel[EvaluationResult],
    ):
        self._chat_model = chat_model

    @map_pipeline_exceptions
    async def execute(self, data: PragmaticSyntaticInput) -> EvaluationResult:
        return await self._chat_model.invoke(
            PRAGMATIC_SYNTACTIC_EVALUATOR_REQUEST.format(
                diagram=data.usecase_diagram.model_dump_json()
            ),
            LLMRoles.USER,
        )
