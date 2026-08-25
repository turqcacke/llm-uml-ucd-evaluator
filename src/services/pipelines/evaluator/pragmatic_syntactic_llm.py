from dataclasses import dataclass

from src.model.domain import EvaluationResult, UseCaseDiagramPresentation
from src.model.domain.evaluation import EvaluationRule
from src.model.llm.context import LLMRoles
from src.services.llm_client import ChatModel
from src.services.shared.evaluation_rules import SYNTACTIC_RULES
from src.services.shared.prompts import PRAGMATIC_SYNTACTIC_EVALUATOR_REQUEST

from ..base import BasePipeline, map_pipeline_exceptions


@dataclass(frozen=True)
class PragmaticSyntacticInput:
    use_case_diagram: UseCaseDiagramPresentation


class PragmaticSyntacticLlmEvaluator(
    BasePipeline[PragmaticSyntacticInput, EvaluationResult]
):
    def __init__(self, chat_model: ChatModel[EvaluationResult]):
        self._chat_model = chat_model

    @map_pipeline_exceptions
    async def execute(self, data: PragmaticSyntacticInput) -> EvaluationResult:
        result = await self._chat_model.invoke(
            PRAGMATIC_SYNTACTIC_EVALUATOR_REQUEST.format(
                diagram=data.use_case_diagram.model_dump_json()
            ),
            LLMRoles.USER,
        )
        return result.model_copy(
            update={
                "applied_rules": [
                    EvaluationRule(rule_id, content)
                    for rule_id, content in SYNTACTIC_RULES.items()
                ]
            }
        )
