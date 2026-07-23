from typing import Self
from uuid import uuid4

from pydantic import BaseModel, Field, model_validator
from pydantic.json_schema import SkipJsonSchema

from .node import Node, NodeType
from .relation import NodeRelation


class UseCaseDiagramPresentation(BaseModel):
    """Use case diagram graph with derived node groups."""

    id: SkipJsonSchema[str] = Field(
        default_factory=lambda: uuid4().hex,
        description="App-generated diagram ID.",
    )

    nodes: set[Node] = Field(
        description="All nodes; IDs must be unique compact strings."
    )
    relations: set[NodeRelation] = Field(
        description="All relations; IDs must be unique compact strings."
    )

    actors: SkipJsonSchema[set[str]] = Field(
        default_factory=set,
        description="Actor node IDs; derived during validation.",
    )
    usecases: SkipJsonSchema[set[str]] = Field(
        default_factory=set,
        description="Use case node IDs; derived during validation.",
    )
    notes: SkipJsonSchema[set[str]] = Field(
        default_factory=set,
        description="Note node IDs; derived during validation.",
    )
    others: SkipJsonSchema[set[str]] = Field(
        default_factory=set,
        description="Other node IDs; derived during validation.",
    )
    systems: SkipJsonSchema[set[str]] = Field(
        default_factory=set,
        description="System node IDs; derived during validation.",
    )
    external_systems: SkipJsonSchema[set[str]] = Field(
        default_factory=set,
        description="External system node IDs; derived during validation.",
    )

    def actor_cnt(self) -> int:
        return len(self.actors)

    def usecase_cnt(self) -> int:
        return len(self.usecases)

    def note_cnt(self) -> int:
        return len(self.notes)

    def other_cnt(self) -> int:
        return len(self.others)

    def system_cnt(self) -> int:
        return len(self.systems)

    def external_system_cnt(self) -> int:
        return len(self.external_systems)

    @model_validator(mode="after")
    def distribute_nodes(self) -> Self:
        stores = {
            NodeType.ACTOR: self.actors,
            NodeType.USECASE: self.usecases,
            NodeType.NOTE: self.notes,
            NodeType.SYSTEM: self.systems,
            NodeType.EXTERNAL_SYSTEM: self.external_systems,
            NodeType.OTHER: self.others,
        }
        for store in stores.values():
            store.clear()

        for node in self.nodes:
            stores.get(node.type, self.others).add(node.id)
        return self
