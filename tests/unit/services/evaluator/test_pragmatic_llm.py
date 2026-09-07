import pytest

from src.model.domain import (
    Node,
    NodeRelation,
    NodeRelationType,
    NodeType,
    UseCaseDiagramPresentation,
)
from src.model.domain.evaluation import (
    NamingUnderstandabilityScore,
    NodeNamingEvaluation,
    PragmaticEvaluationResult,
)
from src.services.evaluator.pragmatic_llm import (
    PragmaticInput,
    PragmaticLlmEvaluator,
)
from src.services.exceptions import (
    LlmRequestError,
    LlmResponseError,
    UseCaseError,
)
from src.services.ports import LLMRoles
from src.services.shared.prompts import PRAGMATIC_EVALUATOR_REQUEST


class FakeChatModel:
    def __init__(self, result: PragmaticEvaluationResult | Exception) -> None:
        self.result = result
        self.calls: list[tuple[str, LLMRoles]] = []

    async def invoke(
        self, prompt: str, role: LLMRoles
    ) -> PragmaticEvaluationResult:
        self.calls.append((prompt, role))
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


@pytest.mark.anyio
@pytest.mark.parametrize(
    "description",
    [None, "", "A customer places an order through Payment API."],
)
async def test_evaluator_sends_graph_and_preserves_llm_scores(
    description,
):
    diagram = UseCaseDiagramPresentation(
        nodes=[
            Node(
                uid="actor",
                name="Customer",
                type=NodeType.ACTOR,
            ),
            Node(uid="usecase", name=" \t\n", type=NodeType.USECASE),
            Node(uid="payment", name="Stripe", type=NodeType.ACTOR),
            Node(
                uid="boundary",
                name="Shop",
                type=NodeType.SYSTEM_BOUNDARY,
            ),
            Node(uid="note", name="Note", type=NodeType.NOTE),
            Node(uid="other", name="Other", type=NodeType.OTHER),
        ],
        relations=[
            NodeRelation(
                uid="association",
                source="actor",
                target="usecase",
                type=NodeRelationType.ASSOCIATION,
            )
        ],
    )
    response = PragmaticEvaluationResult(
        nodes=[
            NodeNamingEvaluation(
                uid=uid, score=NamingUnderstandabilityScore.HIGH
            )
            for uid in ("payment", "actor", "usecase")
        ]
    )
    chat_model = FakeChatModel(response)
    evaluator = PragmaticLlmEvaluator(chat_model)
    result = await evaluator.execute(PragmaticInput(diagram, description))
    assert {node.uid: node.score for node in result.nodes} == {
        "actor": 3,
        "usecase": 3,
        "payment": 3,
    }
    assert all(node.score == 3 for node in response.nodes)
    [(prompt, role)] = chat_model.calls
    assert prompt == PRAGMATIC_EVALUATOR_REQUEST.format(
        candidate=diagram.model_dump_json(include={"nodes", "relations"}),
        description=description or "",
    )
    assert role == LLMRoles.USER
    assert await evaluator.execute(PragmaticInput(diagram)) == result


@pytest.mark.anyio
@pytest.mark.parametrize(
    "uids",
    [
        [],
        ["foreign"],
        ["actor", "actor"],
        ["actor", "foreign"],
        ["actor", "boundary"],
    ],
)
async def test_evaluator_rejects_missing_duplicate_or_foreign_naming_uids(
    uids,
):
    chat_model = FakeChatModel(
        PragmaticEvaluationResult(
            nodes=[
                NodeNamingEvaluation(
                    uid=uid, score=NamingUnderstandabilityScore.HIGH
                )
                for uid in uids
            ]
        )
    )
    with pytest.raises(LlmResponseError, match="exactly one"):
        await PragmaticLlmEvaluator(chat_model).execute(
            PragmaticInput(
                UseCaseDiagramPresentation(
                    nodes=[
                        Node(
                            uid="actor", name="Customer", type=NodeType.ACTOR
                        ),
                        Node(
                            uid="boundary",
                            name="Shop",
                            type=NodeType.SYSTEM_BOUNDARY,
                        ),
                    ],
                    relations=[],
                )
            )
        )


@pytest.mark.anyio
@pytest.mark.parametrize(
    "error",
    [RuntimeError("Evaluator failed"), LlmRequestError("Evaluator failed")],
)
async def test_evaluator_preserves_provider_errors_and_maps_unexpected_errors(
    error,
):
    with pytest.raises(
        (UseCaseError, LlmRequestError), match="Evaluator failed"
    ) as info:
        await PragmaticLlmEvaluator(FakeChatModel(error)).execute(
            PragmaticInput(UseCaseDiagramPresentation(nodes=[], relations=[]))
        )
    if isinstance(error, LlmRequestError):
        assert info.value is error
    else:
        assert info.value.original is error
