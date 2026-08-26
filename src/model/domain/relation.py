from enum import StrEnum
from typing import TYPE_CHECKING, override

from pydantic import BaseModel, Field

from .lib import csv_head, csv_row

if TYPE_CHECKING:
    from .interfaces.compressable import Compressable


class NodeRelationType(StrEnum):
    """Diagram relation kind."""

    ASSOCIATION = "association"
    EXTEND = "extend"
    INCLUDE = "include"
    GENERALIZATION = "generalization"


class NodeRelation(BaseModel):
    """Typed relation between two graph nodes."""

    uid: str = Field(description="Unique compact relation UID, such as '1'.")
    source: str = Field(description="Source node UID.")
    target: str = Field(description="Target node UID.")
    type: NodeRelationType = Field(description="Relation kind.")

    @override
    def __hash__(self) -> int:
        return hash(self.uid)

    def pattern(self) -> str:
        return csv_head(("uid", "source", "target", "type"))

    def compress(self) -> str:
        values = (self.uid, self.source, self.target, self.type.value)
        return csv_row(values)


if TYPE_CHECKING:
    _compressable_type: type[Compressable] = NodeRelation
