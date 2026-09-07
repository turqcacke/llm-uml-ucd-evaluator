import json
from pathlib import Path

import pytest
from dishka import make_async_container
from pydantic import BaseModel
from pymongo import MongoClient

from src.config import get_settings
from src.controller.di import (
    ChatModelProvider,
    DiagramAssessmentProvider,
    EvaluatorProvider,
    ExtractorProvider,
    MatcherProvider,
)
from src.controller.di.mongo import MongoProvider
from src.infrastructure.langchain import chat_model
from src.model.domain import PragmaticEvaluationResult
from src.model.domain.evaluation import (
    NamingUnderstandabilityScore,
    NodeNamingEvaluation,
)
from src.model.domain.matching import MinMatching, NodeMatch


class FakeLanguageModel:
    def __init__(self, naming_score: NamingUnderstandabilityScore) -> None:
        self.naming_score = naming_score
        self.response_type: type[BaseModel] = BaseModel

    def with_structured_output(
        self, response_type: type[BaseModel], **_: object
    ) -> "FakeLanguageModel":
        self.response_type = response_type
        return self

    async def ainvoke(self, _: object) -> BaseModel:
        if self.response_type is MinMatching:
            return MinMatching(
                node_matches=[NodeMatch(reference_uid="r", candidate_uid="c")],
                relation_matches=[],
            )
        if self.response_type is PragmaticEvaluationResult:
            return PragmaticEvaluationResult(
                nodes=[
                    NodeNamingEvaluation(
                        uid="c",
                        score=self.naming_score,
                    )
                ],
            )
        raise AssertionError(f"Unexpected response type {self.response_type}")


def _apollon(node_uid: str, name: str = "Customer") -> str:
    return json.dumps(
        {
            "model": {
                "elements": {
                    node_uid: {
                        "id": node_uid,
                        "name": name,
                        "type": "UseCaseActor",
                        "owner": None,
                        "bounds": {"x": 0, "y": 0},
                    }
                },
                "relationships": {},
            }
        }
    )


@pytest.mark.parametrize(
    "name, syntax_rate, naming_score",
    [("Customer", 0, 3), (" \t", 0.5, 1)],
)
def test_real_di_cli_persists_result_by_returned_uid(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mongo_test_uri: str,
    name: str,
    syntax_rate: float,
    naming_score: int,
) -> None:
    from src.controller.scripts import run_apollon_to_apollon_assessment

    for prefix in ("EXTRACTOR", "MATCHER", "EVALUATOR"):
        monkeypatch.setenv(f"{prefix}_MODEL", f"test-{prefix.lower()}")
        monkeypatch.setenv(f"{prefix}_API_KEY", "test-key")
    monkeypatch.setattr(
        chat_model,
        "init_chat_model",
        lambda **_: FakeLanguageModel(
            NamingUnderstandabilityScore(naming_score)
        ),
    )
    get_settings.cache_clear()
    container = make_async_container(
        ChatModelProvider(),
        ExtractorProvider(),
        MatcherProvider(),
        EvaluatorProvider(),
        MongoProvider(),
        DiagramAssessmentProvider(),
    )
    monkeypatch.setattr(
        run_apollon_to_apollon_assessment,
        "app_container",
        container,
    )
    reference = tmp_path / "reference.json"
    candidate = tmp_path / "candidate.json"
    output_directory = tmp_path / "results"
    reference.write_text(_apollon("r"), "utf-8")
    candidate.write_text(_apollon("c", name), "utf-8")

    try:
        assert (
            run_apollon_to_apollon_assessment.main(
                [
                    str(reference),
                    str(candidate),
                    "--results-path",
                    str(output_directory),
                ]
            )
            == 0
        )
        [output_file] = output_directory.iterdir()
        response = json.loads(output_file.read_text("utf-8"))
        assert "matching" not in response
        assert response["reference_uid"]
        assert response["candidate_uid"]
        assert response["syntactic_error_rate"] == syntax_rate
        assert response["naming_understandability_score"] == naming_score
        assert response["evaluation"] == {
            "syntactic": {
                "nodes": [
                    {
                        "uid": "c",
                        "checks": {
                            "name_present": bool(name.strip()),
                            "parent_exists": True,
                        },
                    }
                ],
                "relations": [],
            },
            "pragmatic": {"nodes": [{"uid": "c", "score": naming_score}]},
        }

        with MongoClient(mongo_test_uri) as client:
            database = client.get_default_database()
            stored = database["diagram_assessments"].find_one(
                {"uid": response["uid"]}
            )
            assert stored is not None
            assert stored["reference_uid"]
            assert stored["candidate_uid"]
            assert stored["evaluation"] == response["evaluation"]
            assert stored["matching"]["node_matches"] == [
                {"reference_uid": "r", "candidate_uid": "c"}
            ]
            assert (
                database["use_case_diagram_presentations"].count_documents({})
                == 2
            )
    finally:
        get_settings.cache_clear()
