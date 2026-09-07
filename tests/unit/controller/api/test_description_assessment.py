import asyncio
from collections.abc import AsyncIterator
from decimal import Decimal
from typing import Any, cast

import pytest
from dishka import Provider, Scope, provide
from fastapi import HTTPException
from httpx import ASGITransport, AsyncClient
from pydantic import ValidationError

from src.config import ApiSettings, Environment, Settings
from src.controller.api.app import create_app
from src.controller.di import make_api_container
from src.model.domain import (
    ElementSyntacticEvaluation,
    EvaluationResult,
    ExtendedMatching,
    MetricsWithEvaluation,
    NamingUnderstandabilityScore,
    Node,
    NodeNamingEvaluation,
    NodeRelation,
    NodeRelationType,
    NodeType,
    PragmaticEvaluationResult,
    SyntacticEvaluationResult,
    UseCaseDiagramPresentation,
)
from src.model.domain.matching import NodeMatch
from src.services.diagram_assessment import (
    ApollonToApollonAssessment,
    ApollonToApollonAssessmentInput,
    AssessmentWriteRepository,
    DescriptionReferenceAssessment,
    DescriptionReferenceAssessmentInput,
)
from src.services.evaluator import (
    PragmaticLlmEvaluator,
    SyntacticDiagramEvaluator,
)
from src.services.exceptions import (
    BaseAppException,
    ConfigError,
    ConversionError,
    LlmRequestError,
    LlmResponseError,
    RateLimitError,
    ReferenceNotAllowedError,
    UseCaseError,
)
from src.services.extractor import ApollonJsonExtractor, DescriptionExtractor
from src.services.matcher import UseCaseDiagramMatcher
from src.services.ports import UnitOfWork


def make_async_container(
    *providers: Provider,
    settings: ApiSettings | None = None,
):
    return make_api_container(
        *providers, settings=settings or ApiSettings(API_SECRET="secret")
    )


def _candidate() -> dict[str, Any]:
    return {
        "model": {
            "elements": {
                "actor": {
                    "id": "actor",
                    "name": "Customer",
                    "type": "UseCaseActor",
                    "owner": None,
                    "bounds": {"x": 0, "y": 0},
                    "editorField": True,
                }
            },
            "relationships": {},
            "editorField": True,
        },
        "editorField": True,
    }


class FakeAssessment:
    def __init__(self, *, candidate_is_allowed: bool = True) -> None:
        self.calls: list[
            DescriptionReferenceAssessmentInput
            | ApollonToApollonAssessmentInput
        ] = []
        self.candidate_is_allowed = candidate_is_allowed

    async def execute(
        self,
        data: DescriptionReferenceAssessmentInput
        | ApollonToApollonAssessmentInput,
    ) -> MetricsWithEvaluation:
        self.calls.append(data)
        reference = UseCaseDiagramPresentation(
            uid="reference-1",
            nodes=[
                Node(
                    uid="shared-id",
                    name="Customer",
                    type=NodeType.ACTOR,
                )
            ],
            relations=[
                NodeRelation(
                    uid="shared-id",
                    source="shared-id",
                    target="shared-id",
                    type=NodeRelationType.ASSOCIATION,
                )
            ],
        )
        candidate = UseCaseDiagramPresentation(
            uid="candidate-1",
            nodes=[Node(uid="candidate-node", name="", type=NodeType.ACTOR)],
            relations=[
                NodeRelation(
                    uid="candidate-node",
                    source="candidate-node",
                    target="candidate-node",
                    type=NodeRelationType.ASSOCIATION,
                )
            ],
        )
        evaluation = None
        matching = None
        if self.candidate_is_allowed:
            evaluation = EvaluationResult(
                syntactic=SyntacticEvaluationResult(
                    nodes=[
                        ElementSyntacticEvaluation(
                            uid="candidate-node",
                            checks={"name_present": False},
                        )
                    ],
                    relations=[
                        ElementSyntacticEvaluation(
                            uid="candidate-node",
                            checks={"endpoints_exist": True},
                        )
                    ],
                ),
                pragmatic=PragmaticEvaluationResult(
                    nodes=[
                        NodeNamingEvaluation(
                            uid="candidate-node",
                            score=NamingUnderstandabilityScore.LOW,
                        )
                    ]
                ),
            )
            matching = ExtendedMatching(
                reference=reference,
                candidate=candidate,
                node_matches=[
                    NodeMatch(
                        reference_uid="shared-id",
                        candidate_uid="candidate-node",
                    )
                ],
                relation_matches=[],
            )
        return MetricsWithEvaluation(
            uid=f"assessment-{len(self.calls)}",
            reference_uid="reference-1",
            candidate_uid="candidate-1",
            candidate_is_allowed=self.candidate_is_allowed,
            redundancy_rate=Decimal("0.1234565"),
            completeness_rate=Decimal(1),
            semantic_precision=Decimal(1),
            semantic_f1_score=Decimal(1),
            syntactic_error_rate=Decimal(0),
            naming_understandability_score=Decimal(3),
            reference_complexity=Decimal(0),
            candidate_complexity=Decimal(2),
            complexity_difference=Decimal(2),
            complexity_deviation_rate=Decimal("Infinity"),
            evaluation=evaluation,
            matching=matching,
            reference=reference,
        )


class FailingAssessment:
    def __init__(self, error: Exception) -> None:
        self.error = error

    async def execute(self, _: object) -> Any:
        raise self.error


class SpecializedUseCaseError(UseCaseError):
    pass


def _request(reference: object = "x" * 100) -> dict[str, object]:
    return {
        "type": "description",
        "reference": reference,
        "candidate": _candidate(),
    }


def _apollon_export() -> dict[str, Any]:
    export = _candidate()
    export["id"] = "editor-export"
    export["model"]["version"] = "3.0.0"
    export["model"]["relationships"] = {
        "relation": {
            "id": "relation",
            "name": "",
            "type": "UseCaseAssociation",
            "owner": None,
            "bounds": {"x": 0, "y": 0, "width": 10, "height": 10},
            "source": {"direction": "Right", "element": "actor"},
            "target": {"direction": "Left", "element": "actor"},
            "path": [{"x": 0, "y": 0}],
            "isManuallyLayouted": False,
        }
    }
    return export


def test_api_configuration_defaults_to_dev_and_rejects_invalid_values() -> (
    None
):
    assert ApiSettings(API_SECRET="secret").ENVIRONMENT is Environment.DEV

    with pytest.raises(ValidationError):
        ApiSettings.model_validate(
            {"API_SECRET": "secret", "ENVIRONMENT": "staging"}
        )


def test_cli_configuration_does_not_require_api_secret() -> None:
    values = {
        f"{role}_{setting}": f"test-{setting.lower()}"
        for role in ("EXTRACTOR", "MATCHER", "EVALUATOR")
        for setting in ("MODEL", "API_KEY")
    }

    settings = Settings.model_validate(values)

    assert not hasattr(settings, "API_SECRET")


class FakeProvider(Provider):
    def __init__(
        self,
        assessment: object,
        apollon_assessment: object | None = None,
    ) -> None:
        super().__init__()
        self.assessment = assessment
        self.apollon = apollon_assessment or assessment

    @provide(scope=Scope.REQUEST)
    def description_assessment(self) -> DescriptionReferenceAssessment:
        return cast(DescriptionReferenceAssessment, self.assessment)

    @provide(scope=Scope.REQUEST)
    def apollon_assessment(self) -> ApollonToApollonAssessment:
        return cast(ApollonToApollonAssessment, self.apollon)


@pytest.mark.anyio
@pytest.mark.parametrize(
    "context_description",
    [None, "", "A customer uses the system."],
)
async def test_apollon_assessment_accepts_editor_export_and_dispatches(
    context_description: str | None,
) -> None:
    description_assessment = FakeAssessment()
    apollon_assessment = FakeAssessment()
    container = make_async_container(
        FakeProvider(description_assessment, apollon_assessment)
    )
    app = create_app(container=container)
    async with app.router.lifespan_context(app):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/api/v1/assessments",
                headers={"X-API-Key": "secret"},
                json={
                    "type": "apollon",
                    "reference": _apollon_export(),
                    "candidate": _candidate(),
                    "description": context_description,
                },
            )

    assert response.status_code == 201
    assert response.json()["data"]["uid"] == "assessment-1"
    assert len(apollon_assessment.calls) == 1
    [call] = apollon_assessment.calls
    assert isinstance(call, ApollonToApollonAssessmentInput)
    assert call.description == context_description
    assert description_assessment.calls == []


@pytest.mark.anyio
@pytest.mark.parametrize(
    "payload",
    [
        {"reference": _apollon_export(), "candidate": _candidate()},
        {
            "type": "unknown",
            "reference": _apollon_export(),
            "candidate": _candidate(),
        },
        {
            "type": "apollon",
            "reference": "x" * 100,
            "candidate": _candidate(),
        },
        {
            "type": "description",
            "reference": _apollon_export(),
            "candidate": _candidate(),
        },
        {
            "type": "apollon",
            "reference": _apollon_export()["model"],
            "candidate": _candidate(),
        },
        {
            "type": "apollon",
            "reference": _apollon_export(),
            "candidate": _candidate(),
            "extra": True,
        },
    ],
)
async def test_discriminator_and_variant_mismatches_are_rejected(
    payload: dict[str, object],
) -> None:
    assessment = FakeAssessment()
    container = make_async_container(FakeProvider(assessment))
    app = create_app(container=container)

    async with app.router.lifespan_context(app):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/api/v1/assessments",
                headers={"X-API-Key": "secret"},
                json=payload,
            )

    assert response.status_code == 422
    assert assessment.calls == []


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("node_id", ""),
        ("node_id", "x" * 257),
        ("node_name", "x" * 513),
        ("node_owner", ""),
        ("relation_id", ""),
        ("relation_name", "x" * 513),
        ("relation_owner", "x" * 257),
        ("source_direction", ""),
        ("source_direction", "x" * 65),
        ("source_element", ""),
        ("source_element", "x" * 257),
    ],
)
async def test_apollon_string_values_outside_boundaries_are_rejected(
    field: str, value: str
) -> None:
    assessment = FakeAssessment()
    container = make_async_container(FakeProvider(assessment))
    app = create_app(container=container)
    reference = _apollon_export()
    node = reference["model"]["elements"]["actor"]
    relation = reference["model"]["relationships"]["relation"]
    targets = {
        "node_id": (node, "id"),
        "node_name": (node, "name"),
        "node_owner": (node, "owner"),
        "relation_id": (relation, "id"),
        "relation_name": (relation, "name"),
        "relation_owner": (relation, "owner"),
        "source_direction": (relation["source"], "direction"),
        "source_element": (relation["source"], "element"),
    }
    target, key = targets[field]
    target[key] = value

    async with app.router.lifespan_context(app):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/api/v1/assessments",
                headers={"X-API-Key": "secret"},
                json={
                    "type": "apollon",
                    "reference": reference,
                    "candidate": _candidate(),
                },
            )

    assert response.status_code == 422
    assert assessment.calls == []


@pytest.mark.anyio
async def test_apollon_string_boundaries_and_disallowed_result_succeed() -> (
    None
):
    assessment = FakeAssessment(candidate_is_allowed=False)
    container = make_async_container(FakeProvider(assessment))
    app = create_app(container=container)
    reference = _apollon_export()
    node = reference["model"]["elements"]["actor"]
    relation = reference["model"]["relationships"]["relation"]
    node.update(id="x" * 256, name="x" * 512, owner="y")
    relation.update(id="x", name="", owner="x" * 256)
    relation["source"].update(direction="x" * 64, element="x" * 256)

    async with app.router.lifespan_context(app):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            responses = [
                await client.post(
                    "/api/v1/assessments",
                    headers={"X-API-Key": "secret"},
                    json={
                        "type": "apollon",
                        "reference": reference,
                        "candidate": _candidate(),
                    },
                )
                for _ in range(2)
            ]

    assert [response.status_code for response in responses] == [201, 201]
    results = [response.json()["data"] for response in responses]
    assert [result["uid"] for result in results] == [
        "assessment-1",
        "assessment-2",
    ]
    assert all(result["candidate_is_allowed"] is False for result in results)
    assert all("reference_uid" not in result for result in results)
    assert all("candidate_uid" not in result for result in results)
    assert all(result["evaluation"] is None for result in results)
    assert all(result["matching"] is None for result in results)
    assert all(result["reference"]["uid"] == "reference-1" for result in results)


@pytest.mark.anyio
async def test_description_assessment_returns_detailed_result() -> (
    None
):
    assessment = FakeAssessment()
    container = make_async_container(FakeProvider(assessment))
    app = create_app(container=container)

    async with app.router.lifespan_context(app):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/api/v1/assessments",
                headers={"X-API-Key": "secret"},
                json={
                    "type": "description",
                    "reference": "x" * 100,
                    "candidate": _candidate(),
                },
            )

    assert response.status_code == 201
    assert response.json() == {
        "ok": True,
        "data": {
            "uid": "assessment-1",
            "candidate_is_allowed": True,
            "redundancy_rate": 0.123456,
            "completeness_rate": 1,
            "semantic_precision": 1,
            "semantic_f1_score": 1,
            "syntactic_error_rate": 0,
            "naming_understandability_score": 3,
            "reference_complexity": 0,
            "candidate_complexity": 2,
            "complexity_difference": 2,
            "complexity_deviation_rate": "Infinity",
            "reference": {
                "uid": "reference-1",
                "nodes": [
                    {
                        "uid": "shared-id",
                        "name": "Customer",
                        "parent": None,
                        "type": "actor",
                    }
                ],
                "relations": [
                    {
                        "uid": "shared-id",
                        "source": "shared-id",
                        "target": "shared-id",
                        "type": "association",
                    }
                ],
            },
            "matching": {
                "node_matches": [
                    {
                        "reference_uid": "shared-id",
                        "candidate_uid": "candidate-node",
                    }
                ],
                "relation_matches": [],
                "missing_nodes": [],
                "redundant_nodes": [],
                "missing_relations": ["shared-id"],
                "redundant_relations": ["candidate-node"],
            },
            "evaluation": {
                "syntactic": {
                    "nodes": [
                        {
                            "uid": "candidate-node",
                            "checks": {"name_present": False},
                        }
                    ],
                    "relations": [
                        {
                            "uid": "candidate-node",
                            "checks": {"endpoints_exist": True},
                        }
                    ],
                },
                "pragmatic": {
                    "nodes": [{"uid": "candidate-node", "score": 1}]
                },
            },
        },
    }
    assert len(assessment.calls) == 1


@pytest.mark.anyio
async def test_authentication_rejects_request_before_assessment() -> None:
    assessment = FakeAssessment()
    container = make_async_container(FakeProvider(assessment))
    app = create_app(container=container)

    async with app.router.lifespan_context(app):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            missing = await client.post("/api/v1/assessments", json=_request())
            incorrect = await client.post(
                "/api/v1/assessments",
                headers={"X-API-Key": "incorrect"},
                json=_request(),
            )

    expected = {
        "ok": False,
        "error_code": "UNAUTHORIZED",
        "error_message": "Authentication is required.",
    }
    assert missing.status_code == incorrect.status_code == 401
    assert missing.json() == incorrect.json() == expected
    assert assessment.calls == []


@pytest.mark.anyio
async def test_assessment_route_is_available_only_under_api_v1() -> None:
    assessment = FakeAssessment()
    container = make_async_container(FakeProvider(assessment))
    app = create_app(container=container)
    headers = {"X-API-Key": "secret"}

    async with app.router.lifespan_context(app):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            current = await client.post(
                "/api/v1/assessments", headers=headers, json=_request()
            )
            former = await client.post(
                "/v1/assessments", headers=headers, json=_request()
            )
            former_stream = await client.post(
                "/v1/assessments/streams", headers=headers, json=_request()
            )

    assert current.status_code == 201
    assert former.status_code == former_stream.status_code == 404
    assert len(assessment.calls) == 1


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("error", "status_code", "error_code"),
    [
        (
            ConversionError("secret input", original=ValueError()),
            422,
            "CONVERSION_ERROR",
        ),
        (
            ReferenceNotAllowedError("secret input", original=ValueError()),
            422,
            "REFERENCE_NOT_ALLOWED",
        ),
        (LlmRequestError("secret provider payload"), 502, "LLM_REQUEST_ERROR"),
        (
            LlmResponseError("secret provider payload"),
            502,
            "LLM_RESPONSE_ERROR",
        ),
        (RateLimitError("secret credentials"), 503, "LLM_RATE_LIMIT_ERROR"),
        (ConfigError("secret configuration"), 500, "CONFIG_ERROR"),
        (
            SpecializedUseCaseError(
                "secret stored details", original=ValueError()
            ),
            500,
            "USE_CASE_ERROR",
        ),
    ],
)
async def test_service_failures_use_safe_error_contract(
    error: BaseAppException, status_code: int, error_code: str
) -> None:
    container = make_async_container(FakeProvider(FailingAssessment(error)))
    app = create_app(container=container)

    async with app.router.lifespan_context(app):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/api/v1/assessments",
                headers={"X-API-Key": "secret"},
                json=_request(),
            )

    assert response.status_code == status_code
    assert response.json() == {
        "ok": False,
        "error_code": error_code,
        "error_message": "The operation could not be completed.",
    }
    assert "secret" not in response.text


@pytest.mark.anyio
async def test_framework_and_internal_failures_use_error_contract() -> None:
    container = make_async_container(
        FakeProvider(FailingAssessment(RuntimeError("secret traceback")))
    )
    app = create_app(container=container)

    @app.get("/invalid-response", response_model=int)
    async def invalid_response() -> str:
        return "secret response"

    @app.get("/custom-http-error")
    async def custom_http_error() -> None:
        raise HTTPException(
            499, "secret framework detail", headers={"X-Retry": "never"}
        )

    transport = ASGITransport(app=app, raise_app_exceptions=False)
    headers = {"X-API-Key": "secret"}
    async with app.router.lifespan_context(app):
        async with AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            missing = await client.get("/missing", headers=headers)
            wrong_method = await client.get("/api/v1/assessments", headers=headers)
            invalid = await client.get("/invalid-response", headers=headers)
            custom = await client.get("/custom-http-error", headers=headers)
            unexpected = await client.post(
                "/api/v1/assessments", headers=headers, json=_request()
            )

    assert missing.status_code == 404
    assert missing.json()["error_code"] == "NOT_FOUND"
    assert wrong_method.status_code == 405
    assert wrong_method.headers["allow"] == "POST"
    assert wrong_method.json()["error_code"] == "METHOD_NOT_ALLOWED"
    assert custom.status_code == 499
    assert custom.headers["x-retry"] == "never"
    assert custom.json()["error_code"] == "HTTP_ERROR"
    assert "secret" not in custom.text
    for response in (invalid, unexpected):
        assert response.status_code == 500
        assert response.json() == {
            "ok": False,
            "error_code": "INTERNAL_ERROR",
            "error_message": "An internal error occurred.",
        }
        assert "secret" not in response.text


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("changes", "field"),
    [
        ({"reference": "x" * 99 + " "}, "reference"),
        ({"reference": "x" * 5001}, "reference"),
        ({"reference": " " * 100}, "reference"),
        ({"reference": 123}, "reference"),
        ({"type": "unknown"}, "type"),
        ({"extra": True}, "extra"),
    ],
)
async def test_invalid_request_does_not_run_assessment(
    changes: dict[str, object], field: str
) -> None:
    assessment = FakeAssessment()
    container = make_async_container(FakeProvider(assessment))
    app = create_app(container=container)
    request = _request()
    request.update(changes)

    async with app.router.lifespan_context(app):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/api/v1/assessments",
                headers={"X-API-Key": "secret"},
                json=request,
            )

    assert response.status_code == 422
    assert response.json()["ok"] is False
    assert response.json()["error_code"] == "VALIDATION_ERROR"
    assert field in response.json()["error_message"]
    assert assessment.calls == []


@pytest.mark.anyio
@pytest.mark.parametrize("length", [100, 5000])
async def test_reference_accepts_non_whitespace_boundaries(
    length: int,
) -> None:
    assessment = FakeAssessment()
    container = make_async_container(FakeProvider(assessment))
    app = create_app(container=container)

    async with app.router.lifespan_context(app):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/api/v1/assessments",
                headers={"X-API-Key": "secret"},
                json=_request(" " + "x" * length + " "),
            )

    assert response.status_code == 201


@pytest.mark.anyio
async def test_missing_reference_and_malformed_json_are_validation_errors() -> (
    None
):
    assessment = FakeAssessment()
    container = make_async_container(FakeProvider(assessment))
    app = create_app(container=container)
    headers = {"X-API-Key": "secret", "Content-Type": "application/json"}

    async with app.router.lifespan_context(app):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            missing = await client.post(
                "/api/v1/assessments",
                headers=headers,
                json={"type": "description", "candidate": _candidate()},
            )
            malformed = await client.post(
                "/api/v1/assessments",
                headers=headers,
                content='{"secret-input-value":',
            )

    assert missing.status_code == malformed.status_code == 422
    assert missing.json()["error_code"] == "VALIDATION_ERROR"
    assert malformed.json()["error_code"] == "VALIDATION_ERROR"
    assert "reference" in missing.json()["error_message"]
    assert "JSON decode error" in malformed.json()["error_message"]
    assert "secret-input-value" not in malformed.text
    assert "https://errors.pydantic.dev" not in missing.text + malformed.text
    assert "detail" not in missing.json() | malformed.json()
    assert assessment.calls == []


@pytest.mark.anyio
async def test_response_waits_for_assessment_completion() -> None:
    assessment = FakeAssessment()
    release = asyncio.Event()
    original_execute = assessment.execute

    async def execute(
        data: DescriptionReferenceAssessmentInput,
    ) -> MetricsWithEvaluation:
        await release.wait()
        return await original_execute(data)

    assessment.execute = execute  # type: ignore[method-assign]
    container = make_async_container(FakeProvider(assessment))
    app = create_app(container=container)

    async with app.router.lifespan_context(app):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            pending = asyncio.create_task(
                client.post(
                    "/api/v1/assessments",
                    headers={"X-API-Key": "secret"},
                    json=_request(),
                )
            )
            await asyncio.sleep(0)
            assert not pending.done()
            release.set()
            response = await pending

    assert response.status_code == 201
    assert len(assessment.calls) == 1


class FakeUseCase:
    def __init__(self, result: Any) -> None:
        self.result = result

    async def execute(self, _: object) -> Any:
        return self.result


class FakeRepository:
    def __init__(self) -> None:
        self.results: list[MetricsWithEvaluation] = []

    async def save_diagram_presentation(
        self, _: UseCaseDiagramPresentation
    ) -> None:
        pass

    async def save_metrics(self, data: MetricsWithEvaluation) -> None:
        self.results.append(data)


class FakeUnitOfWork:
    def __init__(self) -> None:
        self.commits = 0

    async def __aenter__(self) -> "FakeUnitOfWork":
        return self

    async def __aexit__(self, *_: object) -> None:
        pass

    async def commit(self) -> None:
        self.commits += 1

    async def rollback(self) -> None:
        pass


@pytest.mark.anyio
async def test_http_success_observes_persisted_assessment() -> None:
    reference = UseCaseDiagramPresentation(
        nodes=[Node(uid="actor", name="Customer", type=NodeType.ACTOR)],
        relations=[],
    )
    candidate = UseCaseDiagramPresentation(nodes=[], relations=[])
    repository = FakeRepository()
    unit_of_work = FakeUnitOfWork()
    assessment = DescriptionReferenceAssessment(
        cast(DescriptionExtractor, FakeUseCase(reference)),
        cast(ApollonJsonExtractor, FakeUseCase(candidate)),
        cast(UseCaseDiagramMatcher, FakeUseCase(None)),
        cast(PragmaticLlmEvaluator, FakeUseCase(None)),
        cast(AssessmentWriteRepository, repository),
        cast(UnitOfWork, unit_of_work),
        syntactic_evaluator=SyntacticDiagramEvaluator(),
    )
    container = make_async_container(FakeProvider(assessment))
    app = create_app(container=container)

    async with app.router.lifespan_context(app):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/api/v1/assessments",
                headers={"X-API-Key": "secret"},
                json=_request(),
            )

    assert response.status_code == 201
    assert unit_of_work.commits == 1
    assert len(repository.results) == 1
    assert repository.results[0].uid == response.json()["data"]["uid"]


class LifecycleProvider(Provider):
    def __init__(self) -> None:
        super().__init__()
        self.created: list[FakeAssessment] = []
        self.request_cleanups = 0
        self.app_cleanups = 0

    @provide(scope=Scope.APP)
    async def app_resource(self) -> AsyncIterator[str]:
        yield "resource"
        self.app_cleanups += 1

    @provide(scope=Scope.REQUEST)
    async def description_assessment(
        self, app_resource: str
    ) -> AsyncIterator[DescriptionReferenceAssessment]:
        assessment = FakeAssessment()
        self.created.append(assessment)
        yield assessment
        self.request_cleanups += 1

    @provide(scope=Scope.REQUEST)
    def apollon_assessment(
        self, description_assessment: DescriptionReferenceAssessment
    ) -> ApollonToApollonAssessment:
        return cast(ApollonToApollonAssessment, description_assessment)


@pytest.mark.anyio
async def test_dependencies_are_request_scoped_and_cleaned_up() -> None:
    provider = LifecycleProvider()
    container = make_async_container(provider)
    app = create_app(container=container)

    async with app.router.lifespan_context(app):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            for _ in range(2):
                response = await client.post(
                    "/api/v1/assessments",
                    headers={"X-API-Key": "secret"},
                    json=_request(),
                )
                assert response.status_code == 201
        assert len(provider.created) == 2
        assert provider.request_cleanups == 2
        assert provider.app_cleanups == 0

    assert provider.app_cleanups == 1


@pytest.mark.anyio
async def test_api_requires_secret_at_startup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("API_SECRET", "")
    container = make_api_container(FakeProvider(FakeAssessment()))
    original_close = type(container).close
    close_calls = 0

    async def close(target: object) -> None:
        nonlocal close_calls
        close_calls += 1
        await original_close(target)  # type: ignore[arg-type]

    monkeypatch.setattr(type(container), "close", close)
    app = create_app(container=container)

    with pytest.raises(ValueError):
        async with app.router.lifespan_context(app):
            pass
    assert close_calls == 1


@pytest.mark.anyio
@pytest.mark.parametrize("environment", [None, Environment.DEV])
async def test_development_documentation_is_public(
    environment: Environment | None,
) -> None:
    values = {"API_SECRET": "secret"}
    if environment is not None:
        values["ENVIRONMENT"] = environment
    container = make_async_container(
        FakeProvider(FakeAssessment()),
        settings=ApiSettings.model_validate(values),
    )
    app = create_app(container=container)

    async with app.router.lifespan_context(app):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            responses = [
                await client.get(path)
                for path in ("/docs", "/redoc", "/openapi.json")
            ]

    assert all(response.status_code == 200 for response in responses)


@pytest.mark.anyio
async def test_production_disables_docs_and_keeps_assessment_protected() -> (
    None
):
    assessment = FakeAssessment()
    container = make_async_container(
        FakeProvider(assessment),
        settings=ApiSettings(
            API_SECRET="secret", ENVIRONMENT=Environment.PROD
        ),
    )
    app = create_app(container=container)

    async with app.router.lifespan_context(app):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            docs = [
                await client.get(path)
                for path in ("/docs", "/redoc", "/openapi.json")
            ]
            unauthorized = await client.post(
                "/api/v1/assessments", json=_request()
            )
            success = await client.post(
                "/api/v1/assessments",
                headers={"X-API-Key": "secret"},
                json=_request(),
            )

    assert all(response.status_code == 404 for response in docs)
    assert all(
        response.json()["error_code"] == "NOT_FOUND" for response in docs
    )
    assert unauthorized.status_code == 401
    assert success.status_code == 201
