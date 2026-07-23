from src.model.domain.diagram_presentation import UseCaseDiagramPresentation
from src.model.domain.node import Node, NodeType
from src.model.domain.relation import NodeLinkType, NodeRelation


def test_diagram_derives_node_id_groups_outside_llm_schema() -> None:
    schema = UseCaseDiagramPresentation.model_json_schema()

    assert set(schema["properties"]) == {"nodes", "relations"}

    diagram = UseCaseDiagramPresentation(
        nodes={
            Node(id="1", name="Customer", type=NodeType.ACTOR),
            Node(id="2", name="Place order", type=NodeType.USECASE),
            Node(id="3", name="Shop", type=NodeType.SYSTEM),
            Node(
                id="4", name="Payment provider", type=NodeType.EXTERNAL_SYSTEM
            ),
            Node(id="5", name="Checkout note", type=NodeType.NOTE),
            Node(id="6", name="Unclassified", type=NodeType.OTHER),
        },
        relations={
            NodeRelation(
                id="1",
                source="1",
                target="2",
                type=NodeLinkType.ASSOCIATION,
            )
        },
    )

    assert diagram.actors == {"1"}
    assert diagram.usecases == {"2"}
    assert diagram.systems == {"3"}
    assert diagram.external_systems == {"4"}
    assert diagram.notes == {"5"}
    assert diagram.others == {"6"}
    assert len(diagram.relations) == 1
    assert diagram.model_dump(mode="json")["actors"] == ["1"]


def test_graph_schema_describes_every_llm_supplied_field() -> None:
    node_schema = Node.model_json_schema()
    relation_schema = NodeRelation.model_json_schema()

    assert set(node_schema["required"]) == {"id", "name", "type"}
    assert all(
        "description" in field for field in node_schema["properties"].values()
    )
    assert all(
        "description" in field
        for field in relation_schema["properties"].values()
    )
    assert "support" not in {link_type.value for link_type in NodeLinkType}
