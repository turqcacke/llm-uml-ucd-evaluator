from decimal import Decimal
from typing import cast

import pytest
from dishka import Provider, Scope, provide
from httpx import ASGITransport, AsyncClient

from src.config import ApiSettings
from src.controller.api.app import create_app
from src.controller.di import make_api_container
from src.model.domain import MetricsWithEvaluation, Node, NodeType
from src.model.domain.diagram_presentation import UseCaseDiagramPresentation
from src.services.diagram_assessment import (
    GetAssessmentByCandidateId,
    GetAssessmentByUid,
)


def _assessment() -> MetricsWithEvaluation:
    reference = UseCaseDiagramPresentation(
        uid="reference-1",
        nodes=[Node(uid="actor", name="Customer", type=NodeType.ACTOR)],
        relations=[],
    )
    return MetricsWithEvaluation(
        uid="assessment-1",
        reference_uid=reference.uid,
        candidate_uid="candidate-1",
        candidate_is_allowed=True,
        redundancy_rate=Decimal(0),
        completeness_rate=Decimal(1),
        semantic_precision=Decimal(1),
        semantic_f1_score=Decimal(1),
        syntactic_error_rate=Decimal(0),
        naming_understandability_score=Decimal(3),
        reference_complexity=Decimal(0),
        candidate_complexity=Decimal(0),
        complexity_difference=Decimal(0),
        complexity_deviation_rate=Decimal(0),
        reference=reference,
    )


class FakeGetAssessment:
    def __init__(self, results: dict[str, MetricsWithEvaluation]) -> None:
        self.results = results

    async def execute(self, uid: str) -> MetricsWithEvaluation | None:
        return self.results.get(uid)


class FakeProvider(Provider):
    def __init__(self, use_case: FakeGetAssessment) -> None:
        super().__init__()
        self.use_case = use_case

    @provide(scope=Scope.REQUEST)
    def get_assessment(self) -> GetAssessmentByCandidateId:
        return cast(GetAssessmentByCandidateId, self.use_case)


class FakeUidProvider(Provider):
    def __init__(self, use_case: FakeGetAssessment) -> None:
        super().__init__()
        self.use_case = use_case

    @provide(scope=Scope.REQUEST)
    def get_assessment(self) -> GetAssessmentByUid:
        return cast(GetAssessmentByUid, self.use_case)


async def _get(use_case: FakeGetAssessment):
    container = make_api_container(
        FakeProvider(use_case),
        settings=ApiSettings(API_SECRET="secret"),
    )
    app = create_app(container=container)
    async with app.router.lifespan_context(app):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            return await client.get(
                "/api/v1/assessments/candidates/candidate-1",
                headers={"X-API-Key": "secret"},
            )


async def _get_by_uid(use_case: FakeGetAssessment):
    container = make_api_container(
        FakeUidProvider(use_case),
        settings=ApiSettings(API_SECRET="secret"),
    )
    app = create_app(container=container)
    async with app.router.lifespan_context(app):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            return await client.get(
                "/api/v1/assessments/assessment-1",
                headers={"X-API-Key": "secret"},
            )


@pytest.mark.anyio
async def test_get_assessment_returns_metrics_by_candidate_id() -> None:
    use_case = FakeGetAssessment({"candidate-1": _assessment()})

    response = await _get(use_case)

    assert response.status_code == 200
    assert response.json()["data"] == {
        "uid": "assessment-1",
        "candidate_is_allowed": True,
        "redundancy_rate": 0,
        "completeness_rate": 1,
        "semantic_precision": 1,
        "semantic_f1_score": 1,
        "syntactic_error_rate": 0,
        "naming_understandability_score": 3,
        "reference_complexity": 0,
        "candidate_complexity": 0,
        "complexity_difference": 0,
        "complexity_deviation_rate": 0,
        "reference": {
            "uid": "reference-1",
            "nodes": [
                {
                    "uid": "actor",
                    "name": "Customer",
                    "parent": None,
                    "type": "actor",
                }
            ],
            "relations": [],
        },
        "matching": None,
        "evaluation": None,
    }


@pytest.mark.anyio
async def test_get_assessment_returns_not_found_for_unknown_candidate() -> None:
    response = await _get(FakeGetAssessment({}))

    assert response.status_code == 404
    assert response.json() == {
        "ok": False,
        "error_code": "NOT_FOUND",
        "error_message": "Not Found.",
    }


@pytest.mark.anyio
async def test_get_assessment_returns_exact_result_by_uid() -> None:
    use_case = FakeGetAssessment({"assessment-1": _assessment()})

    response = await _get_by_uid(use_case)

    assert response.status_code == 200
    assert response.json()["data"]["uid"] == "assessment-1"


@pytest.mark.anyio
async def test_get_assessment_returns_not_found_for_unknown_uid() -> None:
    response = await _get_by_uid(FakeGetAssessment({}))

    assert response.status_code == 404
