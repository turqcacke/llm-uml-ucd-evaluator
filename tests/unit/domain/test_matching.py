import pytest
from pydantic import ValidationError

from src.model.domain.matching import MatchingResult, NodeMatch


def test_matching_result_uses_reference_and_candidate_semantics() -> None:
    result = MatchingResult(
        node_matches=[NodeMatch(reference_id="1", candidate_id="2")],
        missing_nodes=["3"],
        redundant_nodes=["4"],
        missing_links=["5"],
        redundant_links=["6"],
    )

    assert result.node_matches[0].reference_id == "1"
    assert result.node_matches[0].candidate_id == "2"
    assert result.redundant_nodes == ["4"]
    assert result.redundant_links == ["6"]


def test_matching_result_rejects_missing_differences() -> None:
    with pytest.raises(ValidationError):
        MatchingResult.model_validate({"node_matches": []})
