import pytest
from pydantic import ValidationError

from src.model.domain.diagram_presentation import UseCaseDiagramPresentation
from src.model.domain.node import Node, NodeType
from src.model.domain.relation import NodeRelation, NodeRelationType


def test_diagram_derives_and_serializes_node_id_groups() -> None:
    diagram = UseCaseDiagramPresentation(
        nodes=[
            Node(uid="1", name="Customer", type=NodeType.ACTOR),
            Node(uid="2", name="Place order", type=NodeType.USECASE),
            Node(uid="3", name="Shop", type=NodeType.SYSTEM_BOUNDARY),
            Node(uid="4", name="Payment provider", type=NodeType.ACTOR),
            Node(uid="5", name="Checkout note", type=NodeType.NOTE),
            Node(uid="6", name="Unclassified", type=NodeType.OTHER),
        ],
        relations=[
            NodeRelation(
                uid="1",
                source="1",
                target="2",
                type=NodeRelationType.ASSOCIATION,
            )
        ],
    )

    assert diagram.actors == ["1", "4"]
    assert diagram.usecases == ["2"]
    assert diagram.system_boundaries == ["3"]
    assert diagram.notes == ["5"]
    assert diagram.others == ["6"]
    assert len(diagram.relations) == 1
    assert diagram.model_dump(mode="json")["actors"] == ["1", "4"]


@pytest.mark.parametrize(
    ("nodes", "relations", "error_message"),
    [
        (
            [
                Node(uid="1", name="Customer", type=NodeType.ACTOR),
                Node(uid="1", name="Buyer", type=NodeType.ACTOR),
            ],
            [],
            "Node UIDs must be unique.",
        ),
        (
            [],
            [
                NodeRelation(
                    uid="1",
                    source="1",
                    target="2",
                    type=NodeRelationType.ASSOCIATION,
                ),
                NodeRelation(
                    uid="1",
                    source="2",
                    target="3",
                    type=NodeRelationType.ASSOCIATION,
                ),
            ],
            "Relation UIDs must be unique.",
        ),
    ],
)
def test_diagram_rejects_duplicate_graph_element_uids(
    nodes: list[Node],
    relations: list[NodeRelation],
    error_message: str,
) -> None:
    with pytest.raises(ValidationError, match=error_message):
        UseCaseDiagramPresentation(nodes=nodes, relations=relations)


@pytest.mark.parametrize(
    "node_type, allowed",
    [(None, False)]
    + [
        (
            kind,
            kind in {NodeType.ACTOR, NodeType.USECASE},
        )
        for kind in NodeType
    ],
)
def test_diagram_derives_allowance(
    node_type: NodeType | None, allowed: bool
) -> None:
    diagram = UseCaseDiagramPresentation(
        nodes=[Node(uid="1", name="Element", type=node_type)]
        if node_type is not None
        else [],
        relations=[],
    )

    assert diagram.is_allowed is allowed
