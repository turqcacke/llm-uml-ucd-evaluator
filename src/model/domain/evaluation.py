from enum import IntEnum
from typing import Annotated, NamedTuple

from pydantic import BaseModel, Field


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


class MatchingResult(BaseModel):
    """Diagram node/relation matches and differences."""

    node_matches: list[NodeMatch] = Field(
        description="Pairs ordered [reference_id, candidate_id]."
    )
    missing_nodes: list[str] = Field(
        description="Reference node IDs absent from candidate."
    )
    redundant_nodes: list[str] = Field(
        description="Candidate node IDs unnecessary relative to reference."
    )
    missing_links: list[str] = Field(
        description="Reference relation IDs absent from candidate."
    )
    redundant_links: list[str] = Field(
        description="Candidate relation IDs unnecessary relative to reference."
    )


class NamingUnderstandabilityScore(IntEnum):
    """Element name clarity score."""

    LOW = 1
    MEDIUM = 2
    HIGH = 3


class NodeNamingEvaluation(BaseModel):
    """Candidate node naming evaluation."""

    candidate_node_id: str = Field(description="Evaluated candidate node ID.")
    score: NamingUnderstandabilityScore = Field(
        description=(
            "Naming clarity: 1 unclear; 2 clear, protocol violation; 3 clear, "
            "protocol compliant."
        )
    )
