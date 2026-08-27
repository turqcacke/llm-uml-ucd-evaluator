import pytest

from src.model.domain.diagram_presentation import UseCaseDiagramPresentation
from src.model.domain.exceptions import MatchingError
from src.model.domain.matching import MinMatching, NodeMatch, RelationMatch
from src.model.domain.node import Node, NodeType
from src.model.domain.relation import NodeRelation, NodeRelationType
from src.services.exceptions import (
    LlmRequestError,
    LlmResponseError,
    UseCaseError,
)
from src.services.matcher import (
    UseCaseDiagramMatcher,
    UseCaseDiagramMatcherInput,
)
from src.services.ports import LLMRoles
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
            NodeMatch(reference_uid="reference", candidate_uid="candidate"),
            NodeMatch(reference_uid="note", candidate_uid="candidate"),
            NodeMatch(reference_uid="reference", candidate_uid="other"),
        ],
        relation_matches=[
            RelationMatch(
                reference_uid="reference-relation", candidate_uid="chosen"
            )
        ]
        if match_relation
        else [],
    )
    chat_model = FakeChatModel(result)
    reference = UseCaseDiagramPresentation(
        nodes=[
            Node(uid="reference", name="Buyer", type=NodeType.ACTOR),
            Node(uid="missing", name="Shop", type=NodeType.SYSTEM),
            Node(uid="note", name="Note", type=NodeType.NOTE),
        ],
        relations=[
            NodeRelation(
                uid="reference-relation",
                source="reference",
                target="reference",
                type=NodeRelationType.ASSOCIATION,
            )
        ],
    )
    candidate = UseCaseDiagramPresentation(
        nodes=[
            Node(uid="candidate", name="Customer", type=NodeType.ACTOR),
            Node(uid="redundant", name="Buy", type=NodeType.USECASE),
            Node(uid="other", name="Other", type=NodeType.OTHER),
        ],
        relations=[
            NodeRelation(
                uid=id_,
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
            {"reference_uid": "reference", "candidate_uid": "candidate"}
        ],
        "relation_matches": [
            {
                "reference_uid": "reference-relation",
                "candidate_uid": "chosen",
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
async def test_matcher_reports_invalid_llm_matches_as_response_error() -> None:
    diagram = UseCaseDiagramPresentation(
        nodes=[Node(uid="known", name="Actor", type=NodeType.ACTOR)],
        relations=[],
    )
    llm_result = MinMatching(
        node_matches=[
            NodeMatch(reference_uid="unknown", candidate_uid="known")
        ],
        relation_matches=[],
    )

    with pytest.raises(LlmResponseError) as error_info:
        await UseCaseDiagramMatcher(FakeChatModel(llm_result)).execute(
            UseCaseDiagramMatcherInput(
                reference=diagram,
                candidate=diagram,
            )
        )

    assert isinstance(error_info.value.original, MatchingError)


@pytest.mark.anyio
async def test_matcher_maps_unexpected_error_to_use_case_error() -> None:
    error = RuntimeError("Broken matcher dependency")
    diagram = UseCaseDiagramPresentation(nodes=[], relations=[])

    with pytest.raises(UseCaseError, match="Broken matcher dependency") as info:
        await UseCaseDiagramMatcher(FailingChatModel(error)).execute(
            UseCaseDiagramMatcherInput(
                reference=diagram,
                candidate=diagram,
            )
        )

    assert info.value.original is error
