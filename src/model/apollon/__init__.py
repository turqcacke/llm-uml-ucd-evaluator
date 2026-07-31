from typing import Annotated

from pydantic import BaseModel
from pydantic.fields import Field

from .key_value import Bounds
from .node import ApollonNode, ApollonNodeType
from .relation import (
    ApollonRelation,
    ApollonRelationType,
    PathPoint,
    RelationEndpoint,
)

ApollonItem = Annotated[
    ApollonNode | ApollonRelation, Field(discriminator="type")
]


class ApollonJsonModel(BaseModel):
    elements: dict[str, ApollonItem]


class ApollonJson(BaseModel):
    model: ApollonJsonModel


__all__ = [
    "ApollonItem",
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
