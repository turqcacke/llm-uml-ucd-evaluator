import pytest

from src.model.domain.diagram_presentation import UseCaseDiagramPresentation
from src.model.domain.matching import MinMatching, NodeMatch, RelationMatch
from src.model.domain.node import Node, NodeType
from src.model.domain.relation import NodeRelation, NodeRelationType
from src.model.llm.context import LLMRoles
from src.services.exceptions.llm_client import LlmRequestError
from src.services.exceptions.pipelines import PipelineError
from src.services.pipelines.matcher.use_case_diagram import (
    UseCaseDiagramMatcher,
    UseCaseDiagramMatcherInput,
)
from src.services.shared.prompts import USE_CASE_DIAGRAM_MATCHER_REQUEST


class FakeChatModel:
    def __init__(self, result: MinMatching) -> None:
        self.result = result
        self.calls: list[tuple[str, LLMRoles]] = []

    async def invoke(self, prompt: str, role: LLMRoles) -> MinMatching:
        self.calls.append((prompt, role))
        return self.result


class FailingChatModel:
    def __init__(self, error: Exception) -> None:
        self.error = error

    async def invoke(self, prompt: str, role: LLMRoles) -> MinMatching:
        raise self.error


@pytest.mark.anyio
@pytest.mark.parametrize("match_relation", [True, False])
async def test_matcher_finalizes_semantic_matches(
    match_relation: bool,
) -> None:
    result = MinMatching(
        node_matches=[
            NodeMatch(reference_id="reference", candidate_id="candidate"),
            NodeMatch(reference_id="note", candidate_id="candidate"),
            NodeMatch(reference_id="reference", candidate_id="other"),
        ],
        relation_matches=[
            RelationMatch(
                reference_id="reference-relation", candidate_id="chosen"
            )
        ]
        if match_relation
        else [],
    )
    chat_model = FakeChatModel(result)
    reference = UseCaseDiagramPresentation(
        nodes=[
            Node(id="reference", name="Buyer", type=NodeType.ACTOR),
            Node(id="missing", name="Shop", type=NodeType.SYSTEM),
            Node(id="note", name="Note", type=NodeType.NOTE),
        ],
        relations=[
            NodeRelation(
                id="reference-relation",
                source="reference",
                target="reference",
                type=NodeRelationType.ASSOCIATION,
            )
        ],
    )
    candidate = UseCaseDiagramPresentation(
        nodes=[
            Node(id="candidate", name="Customer", type=NodeType.ACTOR),
            Node(id="redundant", name="Buy", type=NodeType.USECASE),
            Node(id="other", name="Other", type=NodeType.OTHER),
        ],
        relations=[
            NodeRelation(
                id=id_,
                source="candidate",
                target="candidate",
                type=relation_type,
            )
            for id_, relation_type in (
                ("chosen", NodeRelationType.INCLUDE),
                ("alternative", NodeRelationType.ASSOCIATION),
            )
        ],
    )

    actual = await UseCaseDiagramMatcher(chat_model).execute(
        UseCaseDiagramMatcherInput(reference=reference, candidate=candidate)
    )

    assert actual.model_dump() == {
        "node_matches": [
            {"reference_id": "reference", "candidate_id": "candidate"}
        ],
        "relation_matches": [
            {
                "reference_id": "reference-relation",
                "candidate_id": "chosen",
            }
        ]
        if match_relation
        else [],
        "missing_nodes": ["missing"],
        "redundant_nodes": ["redundant"],
        "missing_relations": [] if match_relation else ["reference-relation"],
        "redundant_relations": ["alternative"]
        if match_relation
        else ["chosen", "alternative"],
    }
    assert len(chat_model.calls) == 1
    prompt, role = chat_model.calls[0]
    assert role is LLMRoles.USER
    assert prompt == USE_CASE_DIAGRAM_MATCHER_REQUEST.format(
        reference=reference.model_dump_json(),
        candidate=candidate.model_dump_json(),
    )


@pytest.mark.anyio
async def test_matcher_preserves_service_exception() -> None:
    error = LlmRequestError("Provider failed")
    diagram = UseCaseDiagramPresentation(nodes=[], relations=[])

    with pytest.raises(LlmRequestError) as error_info:
        await UseCaseDiagramMatcher(FailingChatModel(error)).execute(
            UseCaseDiagramMatcherInput(
                reference=diagram,
                candidate=diagram,
            )
        )

    assert error_info.value is error


@pytest.mark.anyio
async def test_matcher_maps_unexpected_error_to_pipeline_error() -> None:
    error = RuntimeError("Broken matcher dependency")
    diagram = UseCaseDiagramPresentation(nodes=[], relations=[])

    with pytest.raises(PipelineError, match="Broken matcher dependency") as info:
        await UseCaseDiagramMatcher(FailingChatModel(error)).execute(
            UseCaseDiagramMatcherInput(
                reference=diagram,
                candidate=diagram,
            )
        )

    assert info.value.original is error
