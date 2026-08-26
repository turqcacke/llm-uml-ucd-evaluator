from dataclasses import dataclass

from src.model.domain import EvaluationResult, UseCaseDiagramPresentation
from src.model.domain.evaluation import EvaluationRule
from src.services.ports import ChatModel, LLMRoles
from src.services.shared.evaluation_rules import SYNTACTIC_RULES
from src.services.shared.prompts import PRAGMATIC_SYNTACTIC_EVALUATOR_REQUEST
from src.services.use_case import UseCase, map_use_case_exceptions


@dataclass(frozen=True)
class PragmaticSyntacticInput:
    use_case_diagram: UseCaseDiagramPresentation


class PragmaticSyntacticLlmEvaluator(
    UseCase[PragmaticSyntacticInput, EvaluationResult]
):
    def __init__(self, chat_model: ChatModel[EvaluationResult]):
        self._chat_model = chat_model

    @map_use_case_exceptions
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
                    EvaluationRule(rule_id=rule_id, content=content)
                    for rule_id, content in SYNTACTIC_RULES.items()
                ]
            }
        )
