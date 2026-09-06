from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from .node import ApollonNodeType
from .relation import ApollonRelationType


class ApollonLayoutDirection(StrEnum):
    LEFT = "Left"
    RIGHT = "Right"
    UP = "Up"
    DOWN = "Down"


class ApollonLayoutSize(BaseModel):
    width: float = Field(gt=0)
    height: float = Field(gt=0)


class ApollonLayoutBounds(BaseModel):
    x: float
    y: float
    width: float = Field(ge=0)
    height: float = Field(ge=0)


class ApollonLayoutPoint(BaseModel):
    x: float
    y: float


class ApollonLayoutEndpoint(BaseModel):
    direction: ApollonLayoutDirection
    element: str


class ApollonLayoutNode(BaseModel):
    id: str
    name: str
    type: ApollonNodeType
    owner: str | None = None
    bounds: ApollonLayoutBounds


class ApollonLayoutRelation(BaseModel):
    model_config = ConfigDict(validate_by_alias=True, validate_by_name=True)

    id: str
    name: str = ""
    type: ApollonRelationType
    owner: str | None = None
    bounds: ApollonLayoutBounds
    path: list[ApollonLayoutPoint]
    source: ApollonLayoutEndpoint
    target: ApollonLayoutEndpoint
    is_manually_layouted: bool = Field(
        default=False,
        alias="isManuallyLayouted",
    )


class ApollonLayout(BaseModel):
    version: Literal["3.0.0"] = "3.0.0"
    type: Literal["UseCaseDiagram"] = "UseCaseDiagram"
    size: ApollonLayoutSize = Field(
        default_factory=lambda: ApollonLayoutSize(width=80, height=80)
    )
    interactive: dict[str, dict[str, object]] = Field(
        default_factory=lambda: {"elements": {}, "relationships": {}}
    )
    elements: dict[str, ApollonLayoutNode] = Field(default_factory=dict)
    relationships: dict[str, ApollonLayoutRelation] = Field(
        default_factory=dict
    )
    assessments: dict[str, object] = Field(default_factory=dict)
