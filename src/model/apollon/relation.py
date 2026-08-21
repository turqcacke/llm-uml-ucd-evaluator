from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field

from .key_value import Bounds


class ApollonRelationType(StrEnum):
    ASSOCIATION = "UseCaseAssociation"
    EXTEND = "UseCaseExtend"
    INCLUDE = "UseCaseInclude"
    GENERALIZATION = "UseCaseGeneralization"
    SUPPORT = "UseCaseSupport"


class RelationEndpoint(BaseModel):
    direction: str
    element: str


class PathPoint(BaseModel):
    x: float
    y: float


class ApollonRelation(BaseModel):
    id: str
    name: str
    type: Literal[
        ApollonRelationType.ASSOCIATION,
        ApollonRelationType.EXTEND,
        ApollonRelationType.INCLUDE,
        ApollonRelationType.GENERALIZATION,
        ApollonRelationType.SUPPORT,
    ]
    owner: str | None = Field(default=None)
    bounds: Bounds
    source: RelationEndpoint
    target: RelationEndpoint
