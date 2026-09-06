import json
from collections.abc import Mapping
from math import isfinite
from typing import Any, Literal, cast, overload

from graphviz import Digraph, escape
from graphviz.backend import CalledProcessError, ExecutableNotFound

from src.model.apollon import (
    ApollonLayout,
    ApollonLayoutBounds,
    ApollonLayoutDirection,
    ApollonLayoutEndpoint,
    ApollonLayoutNode,
    ApollonLayoutPoint,
    ApollonLayoutRelation,
    ApollonLayoutSize,
    ApollonNodeType,
    ApollonRelationType,
)
from src.model.domain import (
    Node,
    NodeRelation,
    NodeRelationType,
    NodeType,
    UseCaseDiagramPresentation,
)
from src.services.converter import BaseConverter
from src.services.exceptions import ConversionError

_PADDING = 40.0
_POINTS_PER_INCH = 72.0
_NODE_SIZES: dict[NodeType, tuple[float, float]] = {
    NodeType.ACTOR: (80.0, 140.0),
    NodeType.USECASE: (160.0, 100.0),
    NodeType.EXTERNAL_SYSTEM: (240.0, 160.0),
}
_BOUNDARY_SIZE = (240.0, 160.0)
_NODE_TYPE_MAP: dict[NodeType, ApollonNodeType] = {
    NodeType.ACTOR: ApollonNodeType.ACTOR,
    NodeType.SYSTEM: ApollonNodeType.SYSTEM,
    NodeType.USECASE: ApollonNodeType.USECASE,
    NodeType.EXTERNAL_SYSTEM: ApollonNodeType.EXTERNAL_SYSTEM,
}
_RELATION_TYPE_MAP: dict[NodeRelationType, ApollonRelationType] = {
    NodeRelationType.ASSOCIATION: ApollonRelationType.ASSOCIATION,
    NodeRelationType.EXTEND: ApollonRelationType.EXTEND,
    NodeRelationType.INCLUDE: ApollonRelationType.INCLUDE,
    NodeRelationType.GENERALIZATION: ApollonRelationType.GENERALIZATION,
}


class _DiagramError(ValueError):
    pass


class _GraphvizOutputError(ValueError):
    pass


class DomainToApollonConverter(
    BaseConverter[UseCaseDiagramPresentation, ApollonLayout]
):
    def convert(self, from_value: UseCaseDiagramPresentation) -> ApollonLayout:
        nodes = {node.uid: node for node in from_value.nodes}
        renderable = {
            uid: node
            for uid, node in nodes.items()
            if node.type in _NODE_TYPE_MAP
        }
        used_boundaries = {
            node.parent
            for node in renderable.values()
            if node.type is NodeType.USECASE and node.parent is not None
        }
        renderable = {
            uid: node
            for uid, node in renderable.items()
            if node.type is not NodeType.SYSTEM or uid in used_boundaries
        }
        if not renderable:
            return ApollonLayout()

        try:
            graph, relations = self._build_graph(from_value, nodes, renderable)
            return self._to_layout(
                _graphviz_json(graph), renderable, relations
            )
        except (_DiagramError, _GraphvizOutputError) as exc:
            raise ConversionError(str(exc), original=exc) from exc

    @staticmethod
    def _build_graph(
        diagram: UseCaseDiagramPresentation,
        nodes: Mapping[str, Node],
        renderable: Mapping[str, Node],
    ) -> tuple[Digraph, list[NodeRelation]]:
        graph = Digraph(
            engine="dot",
            graph_attr={
                "rankdir": "LR",
                "splines": "polyline",
                "margin": "0",
                "pad": "0",
            },
        )
        boundaries = {
            uid: node
            for uid, node in renderable.items()
            if node.type is NodeType.SYSTEM
        }
        clusters: dict[str, Digraph] = {}
        for boundary in boundaries.values():
            cluster = Digraph(name=f"cluster_{boundary.uid}")
            cluster.attr(
                id=boundary.uid,
                label=escape(boundary.name),
                margin=str(int(_PADDING)),
            )
            clusters[boundary.uid] = cluster

        for node in renderable.values():
            if node.type is NodeType.SYSTEM:
                continue
            destination = graph
            if node.type is NodeType.USECASE and node.parent is not None:
                if node.parent not in clusters:
                    raise _DiagramError(
                        f"Use case {node.uid!r} has an unusable owner "
                        f"{node.parent!r}."
                    )
                destination = clusters[node.parent]
            _add_node(destination, node)

        for cluster in clusters.values():
            graph.subgraph(cluster)

        relations: list[NodeRelation] = []
        for relation in diagram.relations:
            missing = {
                endpoint
                for endpoint in (relation.source, relation.target)
                if endpoint not in nodes
            }
            if missing:
                raise _DiagramError(
                    f"Relation {relation.uid!r} has missing endpoints: "
                    f"{', '.join(sorted(missing))}."
                )
            source = nodes[relation.source]
            target = nodes[relation.target]
            if source.uid not in renderable or target.uid not in renderable:
                continue
            if NodeType.SYSTEM in {source.type, target.type}:
                raise _DiagramError(
                    f"Relation {relation.uid!r} uses a System Boundary endpoint."
                )
            graph.edge(
                source.uid,
                target.uid,
                id=relation.uid,
            )
            relations.append(relation)

        return graph, relations

    @staticmethod
    def _to_layout(
        data: object,
        renderable: Mapping[str, Node],
        relations: list[NodeRelation],
    ) -> ApollonLayout:
        root = _mapping(data)
        graph_bounds = _parse_bounds(_required(root, "bb"))
        objects = {
            str(_required(item, "id")): item
            for item in _mapping_list(_required(root, "objects"))
            if "id" in item
        }
        elements = {
            uid: _to_element(
                node,
                _mapping(_required(objects, uid)),
                graph_bounds,
            )
            for uid, node in renderable.items()
        }
        edge_data = {
            str(_required(edge, "id")): edge
            for edge in _mapping_list(root.get("edges", []))
        }
        relationships = {
            relation.uid: _to_relation(
                relation,
                _mapping(_required(edge_data, relation.uid)),
                elements,
                graph_bounds,
            )
            for relation in relations
        }
        width = graph_bounds[2] - graph_bounds[0]
        height = graph_bounds[3] - graph_bounds[1]
        return ApollonLayout(
            size=ApollonLayoutSize(
                width=width + 2 * _PADDING,
                height=height + 2 * _PADDING,
            ),
            elements=elements,
            relationships=relationships,
        )


def _graphviz_json(graph: Digraph) -> object:
    try:
        return json.loads(graph.pipe(format="json").decode())
    except (CalledProcessError, ExecutableNotFound) as exc:
        raise ConversionError(
            "Graphviz could not generate the Apollon Layout.",
            original=exc,
        ) from exc
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ConversionError(
            "Graphviz returned invalid output.", original=exc
        ) from exc


def _add_node(graph: Digraph, node: Node) -> None:
    width, height = _NODE_SIZES[node.type]
    graph.node(
        node.uid,
        label=escape(node.name),
        id=node.uid,
        shape="ellipse" if node.type is NodeType.USECASE else "box",
        width=str(width / _POINTS_PER_INCH),
        height=str(height / _POINTS_PER_INCH),
    )


def _mapping(value: object) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise _GraphvizOutputError("Expected a JSON object.")
    return cast(Mapping[str, Any], value)


def _mapping_list(value: object) -> list[Mapping[str, Any]]:
    if not isinstance(value, list):
        raise _GraphvizOutputError("Expected a JSON array.")
    return [_mapping(item) for item in value]


def _required(data: Mapping[str, Any], key: str) -> Any:
    if key not in data:
        raise _GraphvizOutputError(f"Missing Graphviz field {key!r}.")
    return data[key]


@overload
def _coordinates(value: object, count: Literal[2]) -> tuple[float, float]: ...


@overload
def _coordinates(
    value: object, count: Literal[4]
) -> tuple[float, float, float, float]: ...


def _coordinates(value: object, count: int) -> tuple[float, ...]:
    if not isinstance(value, (list, tuple)) or len(value) != count:
        raise _GraphvizOutputError("Invalid Graphviz coordinates.")
    try:
        coordinates = tuple(float(cast(Any, part)) for part in value)
    except (TypeError, ValueError) as exc:
        raise _GraphvizOutputError("Invalid Graphviz coordinates.") from exc
    if not all(isfinite(coordinate) for coordinate in coordinates):
        raise _GraphvizOutputError("Graphviz coordinates must be finite.")
    return coordinates


def _parse_bounds(value: object) -> tuple[float, float, float, float]:
    if not isinstance(value, str):
        raise _GraphvizOutputError("Invalid Graphviz bounds.")
    bounds = _coordinates(value.split(","), 4)
    if bounds[2] < bounds[0] or bounds[3] < bounds[1]:
        raise _GraphvizOutputError("Graphviz bounds are reversed.")
    return bounds


def _to_layout_point(
    x: float,
    y: float,
    graph_bounds: tuple[float, float, float, float],
) -> ApollonLayoutPoint:
    return ApollonLayoutPoint(
        x=x - graph_bounds[0] + _PADDING,
        y=graph_bounds[3] - y + _PADDING,
    )


def _to_element(
    node: Node,
    data: Mapping[str, Any],
    graph_bounds: tuple[float, float, float, float],
) -> ApollonLayoutNode:
    if node.type is NodeType.SYSTEM:
        x1, y1, x2, y2 = _parse_bounds(_required(data, "bb"))
    else:
        x1, y1, x2, y2 = _node_bounds(data)
    top_left = _to_layout_point(x1, y2, graph_bounds)
    minimum_width, minimum_height = (
        _BOUNDARY_SIZE
        if node.type is NodeType.SYSTEM
        else _NODE_SIZES[node.type]
    )
    width = max(x2 - x1, minimum_width)
    height = max(y2 - y1, minimum_height)
    return ApollonLayoutNode(
        id=node.uid,
        name=node.name,
        type=_NODE_TYPE_MAP[node.type],
        owner=node.parent if node.type is NodeType.USECASE else None,
        bounds=ApollonLayoutBounds(
            x=top_left.x,
            y=top_left.y,
            width=width,
            height=height,
        ),
    )


def _node_bounds(data: Mapping[str, Any]) -> tuple[float, float, float, float]:
    position = _required(data, "pos")
    if not isinstance(position, str):
        raise _GraphvizOutputError("Invalid Graphviz node position.")
    center_x, center_y = _coordinates(position.split(","), 2)
    try:
        width = round(float(_required(data, "width")) * _POINTS_PER_INCH)
        height = round(float(_required(data, "height")) * _POINTS_PER_INCH)
    except (TypeError, ValueError, OverflowError) as exc:
        raise _GraphvizOutputError("Invalid Graphviz node size.") from exc
    if width <= 0 or height <= 0:
        raise _GraphvizOutputError("Graphviz node size must be positive.")
    return (
        center_x - width / 2,
        center_y - height / 2,
        center_x + width / 2,
        center_y + height / 2,
    )


def _to_relation(
    relation: NodeRelation,
    data: Mapping[str, Any],
    elements: Mapping[str, ApollonLayoutNode],
    graph_bounds: tuple[float, float, float, float],
) -> ApollonLayoutRelation:
    points = _parse_route(_required(data, "pos"), graph_bounds)
    source_direction = _travel_direction(points[0], points[1])
    target_direction = _opposite(_travel_direction(points[-2], points[-1]))
    points[0] = _side_midpoint(elements[relation.source], source_direction)
    points[-1] = _side_midpoint(elements[relation.target], target_direction)

    min_x = min(point.x for point in points)
    min_y = min(point.y for point in points)
    max_x = max(point.x for point in points)
    max_y = max(point.y for point in points)
    return ApollonLayoutRelation(
        id=relation.uid,
        type=_RELATION_TYPE_MAP[relation.type],
        bounds=ApollonLayoutBounds(
            x=min_x,
            y=min_y,
            width=max_x - min_x,
            height=max_y - min_y,
        ),
        path=[
            ApollonLayoutPoint(x=point.x - min_x, y=point.y - min_y)
            for point in points
        ],
        source=ApollonLayoutEndpoint(
            direction=source_direction,
            element=relation.source,
        ),
        target=ApollonLayoutEndpoint(
            direction=target_direction,
            element=relation.target,
        ),
    )


def _parse_route(
    value: object,
    graph_bounds: tuple[float, float, float, float],
) -> list[ApollonLayoutPoint]:
    if not isinstance(value, str):
        raise _GraphvizOutputError("Invalid Graphviz relation route.")
    start: tuple[float, float] | None = None
    end: tuple[float, float] | None = None
    route: list[tuple[float, float]] = []
    for token in value.replace(";", " ").split():
        parts = token.split(",")
        if parts[0] in {"s", "e"}:
            marker = _coordinates(parts[1:], 2)
            if parts[0] == "s":
                start = marker
            else:
                end = marker
        else:
            route.append(_coordinates(parts, 2))
    if start is not None:
        route.insert(0, start)
    if end is not None:
        route.append(end)
    points = [_to_layout_point(x, y, graph_bounds) for x, y in route]
    points = [
        point
        for index, point in enumerate(points)
        if index == 0 or point != points[index - 1]
    ]
    if len(points) < 2:
        raise _GraphvizOutputError(
            "Graphviz returned a relation without a route."
        )
    return points


def _travel_direction(
    start: ApollonLayoutPoint,
    end: ApollonLayoutPoint,
) -> ApollonLayoutDirection:
    dx = end.x - start.x
    dy = end.y - start.y
    if abs(dx) >= abs(dy):
        return (
            ApollonLayoutDirection.RIGHT
            if dx >= 0
            else ApollonLayoutDirection.LEFT
        )
    return (
        ApollonLayoutDirection.DOWN if dy >= 0 else ApollonLayoutDirection.UP
    )


def _opposite(direction: ApollonLayoutDirection) -> ApollonLayoutDirection:
    return {
        ApollonLayoutDirection.LEFT: ApollonLayoutDirection.RIGHT,
        ApollonLayoutDirection.RIGHT: ApollonLayoutDirection.LEFT,
        ApollonLayoutDirection.UP: ApollonLayoutDirection.DOWN,
        ApollonLayoutDirection.DOWN: ApollonLayoutDirection.UP,
    }[direction]


def _side_midpoint(
    element: ApollonLayoutNode,
    direction: ApollonLayoutDirection,
) -> ApollonLayoutPoint:
    bounds = element.bounds
    center_x = bounds.x + bounds.width / 2
    center_y = bounds.y + bounds.height / 2
    return {
        ApollonLayoutDirection.LEFT: ApollonLayoutPoint(
            x=bounds.x, y=center_y
        ),
        ApollonLayoutDirection.RIGHT: ApollonLayoutPoint(
            x=bounds.x + bounds.width, y=center_y
        ),
        ApollonLayoutDirection.UP: ApollonLayoutPoint(x=center_x, y=bounds.y),
        ApollonLayoutDirection.DOWN: ApollonLayoutPoint(
            x=center_x, y=bounds.y + bounds.height
        ),
    }[direction]
