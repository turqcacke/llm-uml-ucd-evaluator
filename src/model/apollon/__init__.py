from pydantic import BaseModel

from .key_value import Bounds
from .layout import (
    ApollonLayout,
    ApollonLayoutBounds,
    ApollonLayoutDirection,
    ApollonLayoutEndpoint,
    ApollonLayoutNode,
    ApollonLayoutPoint,
    ApollonLayoutRelation,
    ApollonLayoutSize,
)
from .node import ApollonNode, ApollonNodeType
from .relation import (
    ApollonRelation,
    ApollonRelationType,
    PathPoint,
    RelationEndpoint,
)


class ApollonJsonModel(BaseModel):
    elements: dict[str, ApollonNode]
    relationships: dict[str, ApollonRelation]


class ApollonJson(BaseModel):
    model: ApollonJsonModel


__all__ = [
    "ApollonLayout",
    "ApollonLayoutBounds",
    "ApollonLayoutDirection",
    "ApollonLayoutEndpoint",
    "ApollonLayoutNode",
    "ApollonLayoutPoint",
    "ApollonLayoutRelation",
    "ApollonLayoutSize",
    "ApollonJsonModel",
    "ApollonJson",
    "ApollonNode",
    "ApollonNodeType",
    "ApollonRelation",
    "ApollonRelationType",
    "Bounds",
    "PathPoint",
    "RelationEndpoint",
]
