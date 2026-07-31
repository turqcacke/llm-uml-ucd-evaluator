from enum import StrEnum
from typing import Literal

from pydantic import BaseModel

from .key_value import Bounds


class ApollonNodeType(StrEnum):
    ACTOR = "UseCaseActor"
    SYSTEM = "UseCaseSystem"
    USECASE = "UseCase"
    EXTERNAL_SYSTEM = "UseCaseExternalSystem"
    NOTE = "ColorLegend"
    INVALID = "InvalidNode"


class ApollonNode(BaseModel):
    id: str
    name: str
    type: Literal[
        ApollonNodeType.ACTOR,
        ApollonNodeType.SYSTEM,
        ApollonNodeType.USECASE,
        ApollonNodeType.EXTERNAL_SYSTEM,
        ApollonNodeType.NOTE,
        ApollonNodeType.INVALID,
    ]
    owner: str | None
    bounds: Bounds
