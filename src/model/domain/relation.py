from enum import StrEnum
from typing import TYPE_CHECKING, override

from pydantic import BaseModel, Field

from .lib import csv_head, csv_row

if TYPE_CHECKING:
    from .interfaces.compressable import Compressable


class NodeLinkType(StrEnum):
    """Diagram relation kind."""

    ASSOCIATION = "association"
    EXTEND = "extend"
    INCLUDE = "include"
    GENERALIZATION = "generalization"


class NodeRelation(BaseModel):
    """Typed relation between two graph nodes."""

    id: str = Field(description="Unique compact relation ID, such as '1'.")
    source: str = Field(description="Source node ID.")
    target: str = Field(description="Target node ID.")
    type: NodeLinkType = Field(description="Relation kind.")

    @override
    def __hash__(self) -> int:
        return hash(self.id)

    def pattern(self) -> str:
        return csv_head(("id", "source", "target", "type"))

    def compress(self) -> str:
        values = (self.id, self.source, self.target, self.type.value)
        return csv_row(values)


if TYPE_CHECKING:
    _compressable_type: type[Compressable] = NodeRelation
