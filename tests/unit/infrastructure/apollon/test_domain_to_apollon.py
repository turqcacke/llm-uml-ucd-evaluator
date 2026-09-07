from unittest.mock import patch

import pytest
from graphviz.backend import ExecutableNotFound

from src.infrastructure.apollon import DomainToApollonConverter
from src.model.apollon import (
    ApollonLayoutBounds,
    ApollonLayoutDirection,
    ApollonLayoutRelation,
    ApollonNodeType,
)
from src.model.domain import (
    Node,
    NodeRelation,
    NodeRelationType,
    NodeType,
    UseCaseDiagramPresentation,
)
from src.services.exceptions import ConversionError


def _node(
    uid: str,
    type: NodeType,
    *,
    name: str | None = None,
    parent: str | None = None,
) -> Node:
    return Node(uid=uid, name=name or uid, parent=parent, type=type)


def test_conversion_returns_renderable_layout() -> None:
    diagram = UseCaseDiagramPresentation(
        nodes=[
            _node(
                "actor",
                NodeType.ACTOR,
                name="Actor with a very long label",
            ),
            _node("boundary-1", NodeType.SYSTEM_BOUNDARY),
            _node("inside-1", NodeType.USECASE, parent="boundary-1"),
            _node("boundary-2", NodeType.SYSTEM_BOUNDARY),
            _node("outside", NodeType.USECASE),
            _node("external", NodeType.ACTOR),
        ],
        relations=[
            NodeRelation(
                uid="relation-1",
                source="actor",
                target="inside-1",
                type=NodeRelationType.ASSOCIATION,
            ),
            NodeRelation(
                uid="relation-2",
                source="actor",
                target="inside-1",
                type=NodeRelationType.INCLUDE,
            ),
        ],
    )

    layout = DomainToApollonConverter().convert(diagram)

    assert set(layout.elements) == {
        "actor",
        "boundary-1",
        "inside-1",
        "outside",
        "external",
    }
    assert layout.elements["boundary-1"].type is ApollonNodeType.SYSTEM
    assert layout.elements["external"].type is ApollonNodeType.ACTOR
    assert layout.elements["inside-1"].owner == "boundary-1"
    assert layout.elements["outside"].owner is None
    assert layout.elements["boundary-1"].bounds.width >= 240
    assert layout.elements["boundary-1"].bounds.height >= 160
    assert layout.elements["actor"].bounds.width > 80
    assert set(layout.relationships) == {"relation-1", "relation-2"}
    assert all(relation.path for relation in layout.relationships.values())
    assert all(
        relation.source.element == "actor"
        and relation.target.element == "inside-1"
        for relation in layout.relationships.values()
    )
    assert layout.size.width > 80
    assert layout.size.height > 80

    boundary = layout.elements["boundary-1"].bounds
    inside = layout.elements["inside-1"].bounds
    assert boundary.x <= inside.x
    assert boundary.y <= inside.y
    assert boundary.x + boundary.width >= inside.x + inside.width
    assert boundary.y + boundary.height >= inside.y + inside.height

    boundaries = [layout.elements["boundary-1"].bounds]
    outside = layout.elements["outside"].bounds
    assert not any(
        boundary.x <= outside.x
        and boundary.y <= outside.y
        and boundary.x + boundary.width >= outside.x + outside.width
        and boundary.y + boundary.height >= outside.y + outside.height
        for boundary in boundaries
    )

    for element in layout.elements.values():
        assert element.bounds.x >= 39.5
        assert element.bounds.y >= 39.5
        assert (
            element.bounds.x + element.bounds.width <= layout.size.width - 39.5
        )
        assert (
            element.bounds.y + element.bounds.height
            <= layout.size.height - 39.5
        )

    for relation in layout.relationships.values():
        source_point = _absolute_point(relation, first=True)
        target_point = _absolute_point(relation, first=False)
        assert source_point == _side_midpoint(
            layout.elements[relation.source.element].bounds,
            relation.source.direction,
        )
        assert target_point == _side_midpoint(
            layout.elements[relation.target.element].bounds,
            relation.target.direction,
        )
        assert all(
            0 <= point.x <= relation.bounds.width
            and 0 <= point.y <= relation.bounds.height
            for point in relation.path
        )


def test_conversion_filters_non_renderable_elements_and_relations() -> None:
    diagram = UseCaseDiagramPresentation(
        nodes=[
            _node("actor", NodeType.ACTOR),
            _node("usecase", NodeType.USECASE),
            _node("note", NodeType.NOTE),
            _node("invalid", NodeType.OTHER),
        ],
        relations=[
            NodeRelation(
                uid="kept",
                source="actor",
                target="usecase",
                type=NodeRelationType.ASSOCIATION,
            ),
            NodeRelation(
                uid="note-relation",
                source="actor",
                target="note",
                type=NodeRelationType.ASSOCIATION,
            ),
            NodeRelation(
                uid="invalid-relation",
                source="invalid",
                target="usecase",
                type=NodeRelationType.ASSOCIATION,
            ),
        ],
    )

    layout = DomainToApollonConverter().convert(diagram)

    assert set(layout.elements) == {"actor", "usecase"}
    assert set(layout.relationships) == {"kept"}


def test_empty_conversion_does_not_invoke_graphviz() -> None:
    diagram = UseCaseDiagramPresentation(
        nodes=[_node("note", NodeType.NOTE)],
        relations=[],
    )

    with patch("graphviz.Digraph.pipe") as pipe:
        layout = DomainToApollonConverter().convert(diagram)

    pipe.assert_not_called()
    assert layout.elements == {}
    assert layout.relationships == {}
    assert layout.size.model_dump() == {"width": 80.0, "height": 80.0}


def test_conversion_exposes_expected_failure() -> None:
    diagram = UseCaseDiagramPresentation(
        nodes=[_node("actor", NodeType.ACTOR)],
        relations=[],
    )
    failure = ExecutableNotFound(["dot"])

    with (
        patch("graphviz.Digraph.pipe", side_effect=failure),
        pytest.raises(ConversionError) as raised,
    ):
        DomainToApollonConverter().convert(diagram)

    assert raised.value.original is failure


def test_conversion_does_not_reclassify_programming_errors() -> None:
    diagram = UseCaseDiagramPresentation(
        nodes=[_node("actor", NodeType.ACTOR)],
        relations=[],
    )

    with (
        patch("graphviz.Digraph.pipe", side_effect=ValueError("bug")),
        pytest.raises(ValueError, match="bug"),
    ):
        DomainToApollonConverter().convert(diagram)


@pytest.mark.parametrize(
    "output",
    [
        b'{"bb": "0,0,100,100", "objects": [{"id": "actor"}]}',
        (b'{"bb": "200,0,0,100", "objects": [{"id": "actor"}]}'),
    ],
)
def test_conversion_reclassifies_malformed_graphviz_output(
    output: bytes,
) -> None:
    diagram = UseCaseDiagramPresentation(
        nodes=[_node("actor", NodeType.ACTOR)],
        relations=[],
    )

    with (
        patch(
            "graphviz.Digraph.pipe",
            return_value=output,
        ),
        pytest.raises(ConversionError) as raised,
    ):
        DomainToApollonConverter().convert(diagram)

    assert raised.value.original is not None


def _absolute_point(
    relation: ApollonLayoutRelation, *, first: bool
) -> tuple[float, float]:
    point = relation.path[0 if first else -1]
    bounds = relation.bounds
    return bounds.x + point.x, bounds.y + point.y


def _side_midpoint(
    bounds: ApollonLayoutBounds,
    direction: ApollonLayoutDirection,
) -> tuple[float, float]:
    center_x = bounds.x + bounds.width / 2
    center_y = bounds.y + bounds.height / 2
    return {
        ApollonLayoutDirection.LEFT: (bounds.x, center_y),
        ApollonLayoutDirection.RIGHT: (bounds.x + bounds.width, center_y),
        ApollonLayoutDirection.UP: (center_x, bounds.y),
        ApollonLayoutDirection.DOWN: (center_x, bounds.y + bounds.height),
    }[direction]
