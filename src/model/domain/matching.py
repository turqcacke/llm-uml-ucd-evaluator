from typing import Self

from pydantic import BaseModel, Field, model_validator

from .diagram_presentation import UseCaseDiagramPresentation
from .exceptions import MatchingError
from .node import NodeType


class NodeMatch(BaseModel):
    """Semantically matching reference/candidate node pair."""

    reference_uid: str = Field(description="Matched reference node UID.")
    candidate_uid: str = Field(description="Matched candidate node UID.")


class RelationMatch(BaseModel):
    """Semantically matching reference/candidate relation pair."""

    reference_uid: str = Field(description="Matched reference relation UID.")
    candidate_uid: str = Field(description="Matched candidate relation UID.")


class MinMatching(BaseModel):
    """Semantic node and relation pairs returned by the LLM."""

    node_matches: list[NodeMatch] = Field(
        description="Objects pairing reference and candidate node UIDs."
    )
    relation_matches: list[RelationMatch] = Field(
        description="Objects pairing reference and candidate relation UIDs."
    )


class ExtendedMatching(MinMatching):
    """Matches validated against diagrams, with derived differences."""

    reference: UseCaseDiagramPresentation = Field(exclude=True)
    candidate: UseCaseDiagramPresentation = Field(exclude=True)

    missing_nodes: list[str] = Field(
        default_factory=list,
        description="Reference node UIDs absent from candidate.",
    )
    redundant_nodes: list[str] = Field(
        default_factory=list,
        description="Candidate node UIDs unnecessary relative to reference.",
    )
    missing_relations: list[str] = Field(
        default_factory=list,
        description="Reference relation UIDs absent from candidate.",
    )
    redundant_relations: list[str] = Field(
        default_factory=list,
        description="Candidate relation UIDs unnecessary relative to reference.",
    )

    @model_validator(mode="after")
    def derive_differences(self) -> Self:
        reference = self.reference
        candidate = self.candidate

        excluded = {NodeType.NOTE, NodeType.OTHER}
        reference_node_uids = {
            node.uid for node in reference.nodes if node.type not in excluded
        }
        candidate_node_uids = {
            node.uid for node in candidate.nodes if node.type not in excluded
        }
        self.node_matches = _validated_matches(
            self.node_matches,
            {node.uid for node in reference.nodes},
            {node.uid for node in candidate.nodes},
            reference_excluded_uids={
                node.uid for node in reference.nodes if node.type in excluded
            },
            candidate_excluded_uids={
                node.uid for node in candidate.nodes if node.type in excluded
            },
        )

        reference_relation_uids = {
            relation.uid for relation in reference.relations
        }
        candidate_relation_uids = {
            relation.uid for relation in candidate.relations
        }
        self.relation_matches = _validated_matches(
            self.relation_matches,
            reference_relation_uids,
            candidate_relation_uids,
        )

        matched_reference_node_uids = {
            match.reference_uid for match in self.node_matches
        }
        matched_candidate_node_uids = {
            match.candidate_uid for match in self.node_matches
        }
        matched_reference_relation_uids = {
            match.reference_uid for match in self.relation_matches
        }
        matched_candidate_relation_uids = {
            match.candidate_uid for match in self.relation_matches
        }
        self.missing_nodes = [
            node.uid
            for node in reference.nodes
            if node.uid in reference_node_uids
            and node.uid not in matched_reference_node_uids
        ]
        self.redundant_nodes = [
            node.uid
            for node in candidate.nodes
            if node.uid in candidate_node_uids
            and node.uid not in matched_candidate_node_uids
        ]
        self.missing_relations = [
            relation.uid
            for relation in reference.relations
            if relation.uid not in matched_reference_relation_uids
        ]
        self.redundant_relations = [
            relation.uid
            for relation in candidate.relations
            if relation.uid not in matched_candidate_relation_uids
        ]
        return self


type Match = NodeMatch | RelationMatch


def _validated_matches[T: Match](
    matches: list[T],
    reference_uids: set[str],
    candidate_uids: set[str],
    reference_excluded_uids: set[str] | None = None,
    candidate_excluded_uids: set[str] | None = None,
) -> list[T]:
    reference_excluded_uids = reference_excluded_uids or set()
    candidate_excluded_uids = candidate_excluded_uids or set()
    seen_reference_uids: set[str] = set()
    seen_candidate_uids: set[str] = set()
    included: list[T] = []
    for match in matches:
        reference_uid = match.reference_uid
        candidate_uid = match.candidate_uid
        if (
            reference_uid not in reference_uids
            or candidate_uid not in candidate_uids
        ):
            raise MatchingError("Match contains an unknown element UID.")
        if (
            reference_uid in reference_excluded_uids
            or candidate_uid in candidate_excluded_uids
        ):
            continue
        if reference_uid in seen_reference_uids:
            raise MatchingError("Reference match UIDs must be unique.")
        if candidate_uid in seen_candidate_uids:
            raise MatchingError("Candidate match UIDs must be unique.")
        seen_reference_uids.add(reference_uid)
        seen_candidate_uids.add(candidate_uid)
        included.append(match)
    return included
