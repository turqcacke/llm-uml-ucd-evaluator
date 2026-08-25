from src.model.apollon import (
    ApollonJson,
    ApollonNode,
    ApollonNodeType,
    ApollonRelation,
    ApollonRelationType,
)
from src.model.domain import (
    Node,
    NodeRelation,
    NodeRelationType,
    NodeType,
    UseCaseDiagramPresentation,
)

from .base import BaseConverter


class _NodeConverter(BaseConverter[ApollonNode, Node]):
    _TYPES_MAP = {
        ApollonNodeType.ACTOR: NodeType.ACTOR,
        ApollonNodeType.SYSTEM: NodeType.SYSTEM,
        ApollonNodeType.USECASE: NodeType.USECASE,
        ApollonNodeType.EXTERNAL_SYSTEM: NodeType.EXTERNAL_SYSTEM,
        ApollonNodeType.NOTE: NodeType.NOTE,
        ApollonNodeType.INVALID: NodeType.OTHER,
    }

    def convert(self, from_value: ApollonNode) -> Node:
        return Node(
            id=from_value.id,
            name=from_value.name,
            parent=from_value.owner,
            type=self._TYPES_MAP[from_value.type],
        )


class _NodeRelationConverter(BaseConverter[ApollonRelation, NodeRelation]):
    _TYPES_MAP = {
        ApollonRelationType.ASSOCIATION: NodeRelationType.ASSOCIATION,
        ApollonRelationType.EXTEND: NodeRelationType.EXTEND,
        ApollonRelationType.INCLUDE: NodeRelationType.INCLUDE,
        ApollonRelationType.GENERALIZATION: NodeRelationType.GENERALIZATION,
        ApollonRelationType.SUPPORT: NodeRelationType.ASSOCIATION,
    }

    def convert(self, from_value: ApollonRelation) -> NodeRelation:
        return NodeRelation(
            id=from_value.id,
            source=from_value.source.element,
            target=from_value.target.element,
            type=self._TYPES_MAP[from_value.type],
        )


class ApollonToDomainConverter(
    BaseConverter[ApollonJson, UseCaseDiagramPresentation]
):
    def __init__(self) -> None:
        self._node_converter = _NodeConverter()
        self._relation_converter = _NodeRelationConverter()

    def convert(self, from_value: ApollonJson) -> UseCaseDiagramPresentation:
        nodes = [
            self._node_converter.convert(node)
            for node in from_value.model.elements.values()
        ]
        relations = [
            self._relation_converter.convert(relation)
            for relation in from_value.model.relationships.values()
        ]
        return UseCaseDiagramPresentation(nodes=nodes, relations=relations)
