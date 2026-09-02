import pytest

from src.model.domain import (
    Node,
    NodeRelation,
    NodeRelationType,
    NodeType,
    UseCaseDiagramPresentation,
)
from src.services.evaluator.syntactic_rule_based import (
    SyntacticDiagramEvaluator,
)


@pytest.mark.anyio
async def test_node_checks_use_all_parents_and_return_fresh_scoped_records():
    diagram = UseCaseDiagramPresentation(
        nodes=[
            Node(uid="actor", name="Клиент!", type=NodeType.ACTOR),
            Node(
                uid="external",
                name="Payment API",
                type=NodeType.EXTERNAL_SYSTEM,
                parent="note",
            ),
            Node(
                uid="usecase",
                name=" \t\n",
                type=NodeType.USECASE,
                parent="other",
            ),
            Node(
                uid="system", name="", type=NodeType.SYSTEM, parent="missing"
            ),
            Node(uid="note", name="", type=NodeType.NOTE, parent="missing"),
            Node(uid="other", name="", type=NodeType.OTHER),
        ],
        relations=[
            NodeRelation(
                uid="actor",
                source="missing",
                target="other",
                type=NodeRelationType.INCLUDE,
            )
        ],
    )
    evaluator = SyntacticDiagramEvaluator()
    result = await evaluator.execute(diagram)
    assert result.model_dump() == {
        "nodes": [
            {
                "uid": "actor",
                "checks": {"name_present": True, "parent_exists": True},
            },
            {
                "uid": "external",
                "checks": {"name_present": True, "parent_exists": True},
            },
            {
                "uid": "usecase",
                "checks": {"name_present": False, "parent_exists": True},
            },
            {
                "uid": "system",
                "checks": {"name_present": False, "parent_exists": False},
            },
        ],
        "relations": [{"uid": "actor", "checks": {}}],
    }
    empty = await evaluator.execute(
        UseCaseDiagramPresentation(nodes=[], relations=[])
    )
    again = await evaluator.execute(diagram)
    assert empty.model_dump() == {"nodes": [], "relations": []}
    assert again == result
    assert again is not result
    assert again.nodes[0].checks is not result.nodes[0].checks


@pytest.mark.anyio
@pytest.mark.parametrize(
    "kind",
    [
        NodeType.ACTOR,
        NodeType.EXTERNAL_SYSTEM,
        NodeType.USECASE,
        NodeType.SYSTEM,
    ],
)
@pytest.mark.parametrize(
    "parent,exists",
    [(None, True), ("", False), ("parent", True), ("missing", False)],
)
async def test_parent_existence_applies_to_every_evaluated_node(
    kind, parent, exists
):
    result = await SyntacticDiagramEvaluator().execute(
        UseCaseDiagramPresentation(
            nodes=[
                Node(uid="child", name="Name", type=kind, parent=parent),
                Node(uid="parent", name="Parent", type=NodeType.ACTOR),
            ],
            relations=[],
        )
    )
    assert result.nodes[0].checks == {
        "name_present": True,
        "parent_exists": exists,
    }


@pytest.mark.anyio
async def test_empty_parent_reference_can_identify_existing_node():
    result = await SyntacticDiagramEvaluator().execute(
        UseCaseDiagramPresentation(
            nodes=[Node(uid="", name="Name", type=NodeType.ACTOR, parent="")],
            relations=[],
        )
    )
    assert result.nodes[0].checks == {
        "name_present": True,
        "parent_exists": True,
    }
