import pytest
from pydantic import ValidationError

from src.model.domain.diagram_presentation import UseCaseDiagramPresentation
from src.model.domain.exceptions import MatchingError
from src.model.domain.matching import (
    ExtendedMatching,
    MinMatching,
    NodeMatch,
    RelationMatch,
)
from src.model.domain.node import Node, NodeType
from src.model.domain.relation import NodeRelation, NodeRelationType


def test_min_matching_serializes_matches_as_named_objects() -> None:
    matching = MinMatching(
        node_matches=[
            NodeMatch(reference_uid="reference", candidate_uid="candidate")
        ],
        relation_matches=[
            RelationMatch(reference_uid="reference", candidate_uid="candidate")
        ],
    )

    assert matching.model_dump(mode="json") == {
        "node_matches": [
            {"reference_uid": "reference", "candidate_uid": "candidate"}
        ],
        "relation_matches": [
            {"reference_uid": "reference", "candidate_uid": "candidate"}
        ],
    }


def test_min_matching_rejects_positional_match_arrays() -> None:
    with pytest.raises(ValidationError):
        MinMatching.model_validate(
            {
                "node_matches": [["reference", "candidate"]],
                "relation_matches": [],
            }
        )


@pytest.mark.parametrize("kind", ["node_matches", "relation_matches"])
@pytest.mark.parametrize(
    "pairs, message",
    [
        ([("unknown", "one")], "unknown element UID"),
        ([("one", "unknown")], "unknown element UID"),
        ([("one", "one"), ("one", "two")], "Reference match UIDs"),
        ([("one", "one"), ("two", "one")], "Candidate match UIDs"),
    ],
)
def test_extended_matching_rejects_invalid_pairs(
    kind: str, pairs: list[tuple[str, str]], message: str
) -> None:
    diagram = UseCaseDiagramPresentation(
        nodes=[
            Node(uid=id_, name=id_, type=NodeType.ACTOR)
            for id_ in ("one", "two")
        ],
        relations=[
            NodeRelation(
                uid=id_,
                source="one",
                target="two",
                type=NodeRelationType.ASSOCIATION,
            )
            for id_ in ("one", "two")
        ],
    )
    matching = MinMatching.model_validate(
        {
            "node_matches": [],
            "relation_matches": [],
            kind: [
                {"reference_uid": reference, "candidate_uid": candidate}
                for reference, candidate in pairs
            ],
        }
    )

    with pytest.raises(MatchingError, match=message):
        ExtendedMatching(
            **matching.model_dump(), reference=diagram, candidate=diagram
        )
