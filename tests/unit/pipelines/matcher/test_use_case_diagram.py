import pytest

from src.model.domain.diagram_presentation import UseCaseDiagramPresentation
from src.model.domain.matching import MatchingResult
from src.model.domain.node import Node, NodeType
from src.model.llm.context import LLMRoles
from src.services.pipelines.matcher.use_case_diagram import (
    UseCaseDiagramMatcher,
    UseCaseDiagramMatcherInput,
)


class FakeChatModel:
    def __init__(self, result: MatchingResult) -> None:
        self.result = result
        self.calls: list[tuple[str, LLMRoles]] = []

    async def invoke(self, prompt: str, role: LLMRoles) -> MatchingResult:
        self.calls.append((prompt, role))
        return self.result


@pytest.mark.anyio
async def test_matcher_sends_reference_and_candidate_to_llm() -> None:
    result = MatchingResult(
        node_matches=[],
        missing_nodes=[],
        redundant_nodes=[],
        missing_links=[],
        redundant_links=[],
    )
    chat_model = FakeChatModel(result)
    reference = UseCaseDiagramPresentation(
        nodes=[Node(id="reference", name="Buyer", type=NodeType.ACTOR)],
        relations=[],
    )
    candidate = UseCaseDiagramPresentation(
        nodes=[Node(id="candidate", name="Customer", type=NodeType.ACTOR)],
        relations=[],
    )

    actual = await UseCaseDiagramMatcher(chat_model).execute(
        UseCaseDiagramMatcherInput(reference=reference, candidate=candidate)
    )

    assert actual is result
    assert len(chat_model.calls) == 1
    prompt, role = chat_model.calls[0]
    assert role is LLMRoles.USER
    assert "Reference:" in prompt
    assert reference.model_dump_json() in prompt
    assert "Candidate:" in prompt
    assert candidate.model_dump_json() in prompt
