import pytest

from src.model.domain.diagram_presentation import UseCaseDiagramPresentation
from src.model.domain.matching import MinMatching, NodeMatch, RelationMatch
from src.model.domain.node import Node, NodeType
from src.model.domain.relation import NodeRelation, NodeRelationType
from src.model.llm.context import LLMRoles
from src.services.pipelines.matcher.use_case_diagram import (
    UseCaseDiagramMatcher,
    UseCaseDiagramMatcherInput,
)


class FakeChatModel:
    def __init__(self, result: MinMatching) -> None:
        self.result = result
        self.calls: list[tuple[str, LLMRoles]] = []

    async def invoke(self, prompt: str, role: LLMRoles) -> MinMatching:
        self.calls.append((prompt, role))
        return self.result


@pytest.mark.anyio
@pytest.mark.parametrize("match_relation", [True, False])
async def test_matcher_finalizes_semantic_matches(
    match_relation: bool,
) -> None:
    result = MinMatching(
        node_matches=[
            NodeMatch("reference", "candidate"),
            NodeMatch("note", "candidate"),
            NodeMatch("reference", "other"),
        ],
        relation_matches=[RelationMatch("reference-relation", "chosen")]
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
        "node_matches": [("reference", "candidate")],
        "relation_matches": [("reference-relation", "chosen")]
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
    assert "Reference:" in prompt
    assert reference.model_dump_json() in prompt
    assert "Candidate:" in prompt
    assert candidate.model_dump_json() in prompt
