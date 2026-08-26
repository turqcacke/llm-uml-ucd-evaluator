from enum import StrEnum
from typing import TYPE_CHECKING, override

from pydantic import BaseModel, Field

from .lib import csv_head, csv_row

if TYPE_CHECKING:
    from .interfaces.compressable import Compressable


class NodeType(StrEnum):
    """Use case diagram node role."""

    USECASE = "usecase"
    ACTOR = "actor"
    SYSTEM = "system"
    EXTERNAL_SYSTEM = "external_system"
    NOTE = "note"
    OTHER = "other"


class Node(BaseModel):
    """Typed use case diagram node."""

    uid: str = Field(description="Unique compact node UID, such as '1'.")
    name: str = Field(description="Node label shown on diagram.")
    parent: str | None = Field(
        default=None,
        description="Containing or owning node UID, if any.",
    )
    type: NodeType = Field(
        description=(
            "Node role: usecase, actor, system, external system, note, or other."
        )
    )

    @override
    def __hash__(self) -> int:
        return hash(self.uid)

    def pattern(self) -> str:
        return csv_head(("uid", "name", "parent", "type"))

    def compress(self) -> str:
        values = (self.uid, self.name, self.parent, self.type.value)
        return csv_row(values)


if TYPE_CHECKING:
    _compressable_type: type[Compressable] = Node
