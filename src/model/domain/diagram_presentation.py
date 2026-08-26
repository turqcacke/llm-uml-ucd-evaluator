from typing import Self
from uuid import uuid4

from pydantic import BaseModel, Field, model_validator
from pydantic.json_schema import SkipJsonSchema

from .node import Node, NodeType
from .relation import NodeRelation


class UseCaseDiagramPresentation(BaseModel):
    """Use case diagram graph with derived node groups."""

    uid: SkipJsonSchema[str] = Field(
        default_factory=lambda: uuid4().hex,
        description="App-generated diagram UID.",
    )

    nodes: list[Node] = Field(
        description="All nodes; UIDs must be unique compact strings."
    )
    relations: list[NodeRelation] = Field(
        description="All relations; UIDs must be unique compact strings."
    )

    actors: SkipJsonSchema[list[str]] = Field(
        default_factory=list,
        description="Actor node UIDs; derived during validation.",
    )
    usecases: SkipJsonSchema[list[str]] = Field(
        default_factory=list,
        description="Use case node UIDs; derived during validation.",
    )
    notes: SkipJsonSchema[list[str]] = Field(
        default_factory=list,
        description="Note node UIDs; derived during validation.",
    )
    others: SkipJsonSchema[list[str]] = Field(
        default_factory=list,
        description="Other node UIDs; derived during validation.",
    )
    systems: SkipJsonSchema[list[str]] = Field(
        default_factory=list,
        description="System node UIDs; derived during validation.",
    )
    external_systems: SkipJsonSchema[list[str]] = Field(
        default_factory=list,
        description="External system node UIDs; derived during validation.",
    )

    @property
    def is_allowed(self) -> bool:
        return any(
            node.type
            in {NodeType.ACTOR, NodeType.EXTERNAL_SYSTEM, NodeType.USECASE}
            for node in self.nodes
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
        if len({node.uid for node in self.nodes}) != len(self.nodes):
            raise ValueError("Node UIDs must be unique.")
        if len({relation.uid for relation in self.relations}) != len(
            self.relations
        ):
            raise ValueError("Relation UIDs must be unique.")

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
            stores.get(node.type, self.others).append(node.uid)
        return self
