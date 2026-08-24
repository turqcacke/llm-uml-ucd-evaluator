from typing import Annotated, NamedTuple, Self

from pydantic import BaseModel, Field, model_validator

from .diagram_presentation import UseCaseDiagramPresentation
from .exceptions import MatchingError
from .node import NodeType


class NodeMatch(NamedTuple):
    """Semantically matching reference/candidate node pair."""

    reference_id: Annotated[
        str,
        Field(description="Matched reference node ID."),
    ]
    candidate_id: Annotated[
        str,
        Field(description="Matched candidate node ID."),
    ]


class RelationMatch(NamedTuple):
    """Semantically matching reference/candidate relation pair."""

    reference_id: Annotated[
        str,
        Field(description="Matched reference relation ID."),
    ]
    candidate_id: Annotated[
        str,
        Field(description="Matched candidate relation ID."),
    ]


class MinMatching(BaseModel):
    """Semantic node and relation pairs returned by the LLM."""

    node_matches: list[NodeMatch] = Field(
        description="Pairs ordered [reference_id, candidate_id]."
    )
    relation_matches: list[RelationMatch] = Field(
        description="Pairs ordered [reference_id, candidate_id]."
    )


class ExtendedMatching(MinMatching):
    """Matches validated against diagrams, with derived differences."""

    reference: UseCaseDiagramPresentation = Field(exclude=True)
    candidate: UseCaseDiagramPresentation = Field(exclude=True)

    missing_nodes: list[str] = Field(
        default_factory=list,
        description="Reference node IDs absent from candidate.",
    )
    redundant_nodes: list[str] = Field(
        default_factory=list,
        description="Candidate node IDs unnecessary relative to reference.",
    )
    missing_relations: list[str] = Field(
        default_factory=list,
        description="Reference relation IDs absent from candidate.",
    )
    redundant_relations: list[str] = Field(
        default_factory=list,
        description="Candidate relation IDs unnecessary relative to reference.",
    )

    @model_validator(mode="after")
    def derive_differences(self) -> Self:
        reference = self.reference
        candidate = self.candidate

        excluded = {NodeType.NOTE, NodeType.OTHER}
        reference_nodes = {
            node.id for node in reference.nodes if node.type not in excluded
        }
        candidate_nodes = {
            node.id for node in candidate.nodes if node.type not in excluded
        }
        self.node_matches = _validated_matches(
            self.node_matches,
            {node.id for node in reference.nodes},
            {node.id for node in candidate.nodes},
            reference_excluded={
                node.id for node in reference.nodes if node.type in excluded
            },
            candidate_excluded={
                node.id for node in candidate.nodes if node.type in excluded
            },
        )

        reference_relations = {relation.id for relation in reference.relations}
        candidate_relations = {relation.id for relation in candidate.relations}
        self.relation_matches = _validated_matches(
            self.relation_matches, reference_relations, candidate_relations
        )

        matched_reference_nodes = {
            match.reference_id for match in self.node_matches
        }
        matched_candidate_nodes = {
            match.candidate_id for match in self.node_matches
        }
        matched_reference_relations = {
            match.reference_id for match in self.relation_matches
        }
        matched_candidate_relations = {
            match.candidate_id for match in self.relation_matches
        }
        self.missing_nodes = [
            node.id
            for node in reference.nodes
            if node.id in reference_nodes
            and node.id not in matched_reference_nodes
        ]
        self.redundant_nodes = [
            node.id
            for node in candidate.nodes
            if node.id in candidate_nodes
            and node.id not in matched_candidate_nodes
        ]
        self.missing_relations = [
            relation.id
            for relation in reference.relations
            if relation.id not in matched_reference_relations
        ]
        self.redundant_relations = [
            relation.id
            for relation in candidate.relations
            if relation.id not in matched_candidate_relations
        ]
        return self


type Match = NodeMatch | RelationMatch


def _validated_matches[T: Match](
    matches: list[T],
    reference_ids: set[str],
    candidate_ids: set[str],
    reference_excluded: set[str] | None = None,
    candidate_excluded: set[str] | None = None,
) -> list[T]:
    reference_excluded = reference_excluded or set()
    candidate_excluded = candidate_excluded or set()
    seen_reference: set[str] = set()
    seen_candidate: set[str] = set()
    included: list[T] = []
    for match in matches:
        reference_id, candidate_id = match
        if (
            reference_id not in reference_ids
            or candidate_id not in candidate_ids
        ):
            raise MatchingError("Match contains an unknown element ID.")
        if (
            reference_id in reference_excluded
            or candidate_id in candidate_excluded
        ):
            continue
        if reference_id in seen_reference:
            raise MatchingError("Reference match IDs must be unique.")
        if candidate_id in seen_candidate:
            raise MatchingError("Candidate match IDs must be unique.")
        seen_reference.add(reference_id)
        seen_candidate.add(candidate_id)
        included.append(match)
    return included
