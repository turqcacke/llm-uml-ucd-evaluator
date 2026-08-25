import pytest

from src.model.domain import EvaluationResult, UseCaseDiagramPresentation
from src.model.domain.evaluation import EvaluationRule
from src.model.llm.context import LLMRoles
from src.services.exceptions.pipelines import PipelineError
from src.services.pipelines.evaluator import (
    PragmaticSyntacticInput,
    PragmaticSyntacticLlmEvaluator,
)
from src.services.shared.evaluation_rules import SYNTACTIC_RULES
from src.services.shared.prompts import (
    PRAGMATIC_SYNTACTIC_EVALUATOR_REQUEST,
)


class FakeChatModel:
    def __init__(self, result: EvaluationResult | Exception) -> None:
        self.result = result
        self.calls: list[tuple[str, LLMRoles]] = []

    async def invoke(
        self, prompt: str, role: LLMRoles
    ) -> EvaluationResult:
        self.calls.append((prompt, role))
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


@pytest.mark.anyio
async def test_evaluator_returns_structured_candidate_evaluation() -> None:
    diagram = UseCaseDiagramPresentation(nodes=[], relations=[])
    expected = EvaluationResult(
        node_evaluations=[], relation_evaluations=[], applied_rules=[]
    )
    chat_model = FakeChatModel(expected)

    result = await PragmaticSyntacticLlmEvaluator(chat_model).execute(
        PragmaticSyntacticInput(diagram)
    )

    assert result.node_evaluations == []
    assert result.relation_evaluations == []
    assert result.applied_rules == [
        EvaluationRule(rule_id=rule_id, content=content)
        for rule_id, content in SYNTACTIC_RULES.items()
    ]
    assert chat_model.calls == [
        (
            PRAGMATIC_SYNTACTIC_EVALUATOR_REQUEST.format(
                diagram=diagram.model_dump_json()
            ),
            LLMRoles.USER,
        )
    ]


@pytest.mark.anyio
async def test_evaluator_maps_unexpected_failure() -> None:
    error = RuntimeError("Evaluator failed")

    with pytest.raises(PipelineError, match="Evaluator failed") as info:
        await PragmaticSyntacticLlmEvaluator(FakeChatModel(error)).execute(
            PragmaticSyntacticInput(
                UseCaseDiagramPresentation(nodes=[], relations=[])
            )
        )

    assert info.value.original is error
