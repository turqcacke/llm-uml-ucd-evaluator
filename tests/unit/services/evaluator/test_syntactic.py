import pytest

from src.model.domain import (
    Node,
    NodeRelation,
    NodeRelationType,
    NodeType,
    UseCaseDiagramPresentation,
)
from src.services.evaluator.syntactic_rule_based import (
    EndpointsExist,
    EndpointTypesValid,
    GeneralizationAcyclic,
    IncludeAcyclic,
    NamePresent,
    ParentExists,
    SyntacticDiagramEvaluator,
    apply_rules,
    find_cycles,
)


def _node(
    uid: str,
    type_: NodeType = NodeType.USECASE,
    *,
    name: str = "Name",
    parent: str | None = None,
) -> Node:
    return Node(uid=uid, name=name, parent=parent, type=type_)


def _relation(
    uid: str,
    source: str,
    target: str,
    type_: NodeRelationType = NodeRelationType.GENERALIZATION,
) -> NodeRelation:
    return NodeRelation(uid=uid, source=source, target=target, type=type_)


@pytest.mark.parametrize(
    "name,expected",
    [("Name", True), (" Клиент! ", True), ("", False), (" \t\n", False)],
)
def test_name_present(name: str, expected: bool):
    rule = NamePresent()

    assert rule.rule_id == "name_present"
    assert rule(_node("node", name=name)) is expected


@pytest.mark.parametrize(
    "parent,node_uids,expected",
    [
        (None, set(), True),
        ("parent", {"parent"}, True),
        ("missing", {"parent"}, False),
        ("", {""}, True),
        ("", set(), False),
    ],
)
def test_parent_exists(parent: str | None, node_uids: set[str], expected: bool):
    rule = ParentExists(node_uids)

    assert rule.rule_id == "parent_exists"
    assert rule(_node("child", parent=parent)) is expected


@pytest.mark.parametrize(
    "source,target,expected",
    [
        ("source", "target", True),
        ("missing", "target", False),
        ("source", "missing", False),
        ("missing", "also-missing", False),
    ],
)
def test_endpoints_exist(source: str, target: str, expected: bool):
    rule = EndpointsExist({"source", "target"})

    assert rule.rule_id == "endpoints_exist"
    assert rule(_relation("relation", source, target)) is expected


def test_rule_chain_stops_after_missing_endpoints():
    relation = _relation("relation", "missing", "also-missing")

    assert apply_rules(
        relation,
        (EndpointsExist(set()), EndpointTypesValid({})),
    ) == {"endpoints_exist": False}


@pytest.mark.parametrize(
    "relation_type,source_type,target_type,expected",
    [
        (NodeRelationType.ASSOCIATION, NodeType.ACTOR, NodeType.USECASE, True),
        (NodeRelationType.ASSOCIATION, NodeType.USECASE, NodeType.ACTOR, True),
        (
            NodeRelationType.ASSOCIATION,
            NodeType.EXTERNAL_SYSTEM,
            NodeType.USECASE,
            True,
        ),
        (
            NodeRelationType.ASSOCIATION,
            NodeType.USECASE,
            NodeType.EXTERNAL_SYSTEM,
            True,
        ),
        (NodeRelationType.ASSOCIATION, NodeType.ACTOR, NodeType.ACTOR, False),
        (NodeRelationType.INCLUDE, NodeType.USECASE, NodeType.USECASE, True),
        (NodeRelationType.INCLUDE, NodeType.ACTOR, NodeType.USECASE, False),
        (NodeRelationType.EXTEND, NodeType.USECASE, NodeType.USECASE, True),
        (NodeRelationType.EXTEND, NodeType.USECASE, NodeType.ACTOR, False),
        (
            NodeRelationType.GENERALIZATION,
            NodeType.USECASE,
            NodeType.USECASE,
            True,
        ),
        (
            NodeRelationType.GENERALIZATION,
            NodeType.ACTOR,
            NodeType.ACTOR,
            True,
        ),
        (
            NodeRelationType.GENERALIZATION,
            NodeType.ACTOR,
            NodeType.EXTERNAL_SYSTEM,
            True,
        ),
        (
            NodeRelationType.GENERALIZATION,
            NodeType.EXTERNAL_SYSTEM,
            NodeType.ACTOR,
            True,
        ),
        (
            NodeRelationType.GENERALIZATION,
            NodeType.EXTERNAL_SYSTEM,
            NodeType.EXTERNAL_SYSTEM,
            True,
        ),
        (
            NodeRelationType.GENERALIZATION,
            NodeType.ACTOR,
            NodeType.USECASE,
            False,
        ),
        (
            NodeRelationType.GENERALIZATION,
            NodeType.SYSTEM,
            NodeType.SYSTEM,
            False,
        ),
    ],
)
def test_endpoint_types_valid(
    relation_type: NodeRelationType,
    source_type: NodeType,
    target_type: NodeType,
    expected: bool,
):
    nodes = {
        "source": _node("source", source_type),
        "target": _node("target", target_type),
    }
    rule = EndpointTypesValid(nodes)

    assert rule.rule_id == "endpoint_types_valid"
    assert (
        rule(_relation("relation", "source", "target", relation_type))
        is expected
    )


def test_rule_chain_continues_after_invalid_endpoint_types():
    relation = _relation("relation", "actor", "usecase")
    nodes = {
        "actor": _node("actor", NodeType.ACTOR),
        "usecase": _node("usecase", NodeType.USECASE),
    }

    assert apply_rules(
        relation,
        (
            EndpointsExist(set(nodes)),
            EndpointTypesValid(nodes),
            GeneralizationAcyclic(set()),
        ),
    ) == {
        "endpoints_exist": True,
        "endpoint_types_valid": False,
        "generalization_acyclic": True,
    }


@pytest.mark.parametrize(
    "relations,closing_uids",
    [
        # no cycles
        pytest.param(
            [
                _relation("ab", "a", "b"),
                _relation("bc", "b", "c"),
                _relation("cd", "c", "d"),
            ],
            set(),
            id="no-cycles",
        ),
        # two cycles closing to the same node
        pytest.param(
            [
                _relation("ab", "a", "b"),
                _relation("ba", "b", "a"),
                _relation("ac", "a", "c"),
                _relation("ca", "c", "a"),
            ],
            {"ba", "ca"},
            id="two-cycles-to-one-node",
        ),
        # one indirect cycle
        pytest.param(
            [
                _relation("ab", "a", "b"),
                _relation("bc", "b", "c"),
                _relation("ca", "c", "a"),
            ],
            {"ca"},
            id="one-cycle-to-node",
        ),
        # two cycles closing to different nodes
        pytest.param(
            [
                _relation("ab", "a", "b"),
                _relation("ba", "b", "a"),
                _relation("cd", "c", "d"),
                _relation("dc", "d", "c"),
            ],
            {"ba", "dc"},
            id="two-cycles-to-different-nodes",
        ),
        # self-loop
        pytest.param(
            [_relation("self", "a", "a")],
            {"self"},
            id="self-loop",
        ),
        # edges entering and leaving a cycle
        pytest.param(
            [
                _relation("entry", "entry", "a"),
                _relation("ab", "a", "b"),
                _relation("ba", "b", "a"),
                _relation("exit", "a", "exit"),
            ],
            {"ba"},
            id="edges-entering-and-leaving-cycle",
        ),
        # converging paths without a cycle
        pytest.param(
            [
                _relation("ab", "a", "b"),
                _relation("ac", "a", "c"),
                _relation("bd", "b", "d"),
                _relation("cd", "c", "d"),
            ],
            set(),
            id="diamond-is-acyclic",
        ),
    ],
)
def test_find_cycles(
    relations: list[NodeRelation], closing_uids: set[str]
):
    node_uids = {
        endpoint
        for relation in relations
        for endpoint in (relation.source, relation.target)
    }
    assert {
        relation.uid
        for relation in find_cycles(
            relations, NodeRelationType.GENERALIZATION, node_uids
        )
    } == closing_uids


def test_find_cycles_ignores_other_kinds_and_missing_endpoints():
    # Mixed relation kinds and dangling endpoints cannot form a checked cycle.
    relations = [
        _relation("generalization", "a", "b"),
        _relation("include", "b", "a", NodeRelationType.INCLUDE),
        _relation("dangling", "missing", "a"),
        _relation("reverse-dangling", "a", "missing"),
    ]

    assert (
        find_cycles(
            relations, NodeRelationType.GENERALIZATION, {"a", "b"}
        )
        == set()
    )


def test_cycle_rules_apply_only_to_their_relation_kind():
    include = _relation("include", "a", "a", NodeRelationType.INCLUDE)
    generalization = _relation("generalization", "a", "a")
    include_rule = IncludeAcyclic({include})
    generalization_rule = GeneralizationAcyclic({generalization})

    assert include_rule.rule_id == "include_acyclic"
    assert generalization_rule.rule_id == "generalization_acyclic"
    assert include_rule(include) is False
    assert include_rule(generalization) is None
    assert generalization_rule(generalization) is False
    assert generalization_rule(include) is None


def test_rule_chain_omits_inapplicable_cycle_rule():
    include = _relation("include", "a", "b", NodeRelationType.INCLUDE)

    assert apply_rules(
        include,
        (IncludeAcyclic(set()), GeneralizationAcyclic(set())),
    ) == {
        "include_acyclic": True,
    }


@pytest.mark.anyio
async def test_syntactic_evaluator_composes_relation_rules():
    diagram = UseCaseDiagramPresentation(
        nodes=[
            _node("actor", NodeType.ACTOR, name="", parent="missing"),
            _node("usecase"),
        ],
        relations=[
            _relation(
                "association",
                "actor",
                "usecase",
                NodeRelationType.ASSOCIATION,
            ),
            _relation("forward", "actor", "usecase"),
            _relation("closing", "usecase", "actor"),
            _relation(
                "dangling",
                "missing",
                "usecase",
                NodeRelationType.INCLUDE,
            ),
        ],
    )

    result = await SyntacticDiagramEvaluator().execute(diagram)

    assert [node.checks for node in result.nodes] == [
        {"name_present": False, "parent_exists": False},
        {"name_present": True, "parent_exists": True},
    ]
    assert {relation.uid: relation.checks for relation in result.relations} == {
        "association": {
            "endpoints_exist": True,
            "endpoint_types_valid": True,
        },
        "forward": {
            "endpoints_exist": True,
            "endpoint_types_valid": False,
            "generalization_acyclic": True,
        },
        "closing": {
            "endpoints_exist": True,
            "endpoint_types_valid": False,
            "generalization_acyclic": False,
        },
        "dangling": {"endpoints_exist": False},
    }
