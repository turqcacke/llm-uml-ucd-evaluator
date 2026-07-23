from src.model.domain.evaluation import (
    MatchingResult,
    NamingUnderstandabilityScore,
    NodeMatch,
    NodeNamingEvaluation,
)


def test_evaluation_models_use_reference_and_candidate_semantics() -> None:
    result = MatchingResult(
        node_matches=[NodeMatch(reference_id="1", candidate_id="2")],
        missing_nodes=["3"],
        redundant_nodes=["4"],
        missing_links=["5"],
        redundant_links=["6"],
    )
    evaluation = NodeNamingEvaluation(
        candidate_node_id="2",
        score=NamingUnderstandabilityScore.HIGH,
    )

    assert result.node_matches[0].reference_id == "1"
    assert result.node_matches[0].candidate_id == "2"
    assert result.redundant_nodes == ["4"]
    assert result.redundant_links == ["6"]
    assert evaluation.model_dump(mode="json") == {
        "candidate_node_id": "2",
        "score": 3,
    }


def test_node_match_schema_describes_both_tuple_positions() -> None:
    schema = MatchingResult.model_json_schema()
    pair_items = schema["$defs"]["NodeMatch"]["prefixItems"]

    assert pair_items[0]["description"] == "Matched reference node ID."
    assert pair_items[1]["description"] == "Matched candidate node ID."
