from src.model.domain.lib import csv_head
from src.model.domain.node import Node, NodeType
from src.model.domain.relation import NodeRelation, NodeRelationType


def test_csv_head_returns_csv_header() -> None:
    assert csv_head(("id", "display,name", "type")) == 'id,"display,name",type'


def test_node_compress_returns_csv_pattern_and_value() -> None:
    node = Node(
        uid="node-1",
        name="John, Jr.",
        type=NodeType.ACTOR,
    )

    assert node.uid == "node-1"
    assert node.pattern() == "uid,name,parent,type"
    assert node.compress() == 'node-1,"John, Jr.",,actor'


def test_relation_compress_returns_csv_pattern_and_value() -> None:
    relation = NodeRelation(
        uid="relation-1",
        source="source-1",
        target="target-1",
        type=NodeRelationType.EXTEND,
    )

    assert relation.uid == "relation-1"
    assert relation.pattern() == "uid,source,target,type"
    assert relation.compress() == "relation-1,source-1,target-1,extend"


def test_relation_compress_escapes_csv_values() -> None:
    relation = NodeRelation(
        uid="relation-1",
        source="source,1",
        target='target "1"',
        type=NodeRelationType.ASSOCIATION,
    )

    assert (
        relation.compress()
        == 'relation-1,"source,1","target ""1""",association'
    )
