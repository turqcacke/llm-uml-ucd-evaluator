import asyncio
import json
from collections.abc import AsyncGenerator, AsyncIterator
from decimal import Decimal
from typing import Any, cast

import pytest
from dishka import Provider, Scope, make_async_container, provide
from httpx import ASGITransport, AsyncClient

from src.config import ApiSettings
from src.controller.api.app import create_app
from src.model.domain import (
    AssessmentState,
    EvaluationResult,
    ExtendedMatching,
    MetricsWithEvaluation,
    Node,
    NodeType,
    UseCaseDiagramPresentation,
)
from src.model.domain.evaluation import (
    NamingUnderstandabilityScore,
    NodeEvaluation,
)
from src.model.domain.matching import NodeMatch
from src.services.diagram_assessment import (
    ApollonReferenceAssessment,
    AssessmentWriteRepository,
    DescriptionReferenceAssessment,
)
from src.services.evaluator import PragmaticSyntacticLlmEvaluator
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
                }
            },
            "relationships": {},
        }
    }


def _request(kind: str) -> dict[str, Any]:
    return {
        "type": kind,
        "reference": _candidate() if kind == "apollon" else "x" * 100,
        "candidate": _candidate(),
    }


def _metrics() -> MetricsWithEvaluation:
    return MetricsWithEvaluation(
        uid="assessment-1",
        reference_uid="reference-1",
        candidate_uid="candidate-1",
        candidate_is_allowed=True,
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
        evaluation=None,
        matching=None,
    )


def _diagram(uid: str) -> UseCaseDiagramPresentation:
    return UseCaseDiagramPresentation(
        nodes=[Node(uid=uid, name="Customer", type=NodeType.ACTOR)],
        relations=[],
    )


class FakeAssessment:
    def __init__(self) -> None:
        self.calls: list[object] = []

    async def stream(
        self, data: object
    ) -> AsyncGenerator[tuple[AssessmentState, MetricsWithEvaluation | None]]:
        self.calls.append(data)
        yield AssessmentState.EXTRACTING, None
        yield AssessmentState.ANALYZING, None
        yield AssessmentState.SAVING, None
        yield AssessmentState.COMPLETED, _metrics()
        raise RuntimeError("stream continued after terminal result")


class FailingAssessment:
    def __init__(self, error: Exception) -> None:
        self.error = error

    async def stream(
        self, _: object
    ) -> AsyncGenerator[tuple[AssessmentState, MetricsWithEvaluation | None]]:
        yield AssessmentState.EXTRACTING, None
        raise self.error


class InvalidResultAssessment:
    async def stream(
        self, _: object
    ) -> AsyncGenerator[tuple[AssessmentState, object | None]]:
        yield AssessmentState.COMPLETED, object()


class FakeProvider(Provider):
    def __init__(
        self, description: object, apollon: object | None = None
    ) -> None:
        super().__init__()
        self.description = description
        self.apollon = apollon or description

    @provide(scope=Scope.REQUEST)
    def description_assessment(self) -> DescriptionReferenceAssessment:
        return cast(DescriptionReferenceAssessment, self.description)

    @provide(scope=Scope.REQUEST)
    def apollon_assessment(self) -> ApollonReferenceAssessment:
        return cast(ApollonReferenceAssessment, self.apollon)


def _events(response: str) -> list[tuple[str, dict[str, Any]]]:
    events = []
    for block in response.strip().split("\n\n"):
        fields = dict(line.split(": ", 1) for line in block.splitlines())
        events.append((fields["event"], json.loads(fields["data"])))
    return events


@pytest.mark.anyio
@pytest.mark.parametrize("kind", ["description", "apollon"])
async def test_stream_supports_both_inputs_and_projects_result(kind: str) -> None:
    description = FakeAssessment()
    apollon = FakeAssessment()
    container = make_async_container(FakeProvider(description, apollon))
    app = create_app(
        settings=ApiSettings(API_SECRET="secret"), container=container
    )

    async with app.router.lifespan_context(app):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/v1/assessments/streams",
                headers={"X-API-Key": "secret"},
                json=_request(kind),
            )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    events = _events(response.text)
    assert [(event, data["state"]) for event, data in events] == [
        ("progress", "extracting"),
        ("progress", "analyzing"),
        ("progress", "saving"),
        ("result", "completed"),
    ]
    assert events[-1][1]["data"] == {
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
    }
    selected, unselected = (
        (apollon, description) if kind == "apollon" else (description, apollon)
    )
    assert len(selected.calls) == 1
    assert type(selected.calls[0]).__name__.startswith(kind.capitalize())
    assert unselected.calls == []


@pytest.mark.anyio
@pytest.mark.parametrize("kind", ["description", "apollon"])
async def test_stream_rejects_auth_and_input_before_opening(kind: str) -> None:
    assessment = FakeAssessment()
    container = make_async_container(FakeProvider(assessment))
    app = create_app(
        settings=ApiSettings(API_SECRET="secret"), container=container
    )
    invalid = _request(kind)
    invalid["candidate"] = {"model": {}}

    async with app.router.lifespan_context(app):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            unauthorized = await client.post(
                "/v1/assessments/streams", json=_request(kind)
            )
            incorrect = await client.post(
                "/v1/assessments/streams",
                headers={"X-API-Key": "incorrect"},
                json=_request(kind),
            )
            malformed = await client.post(
                "/v1/assessments/streams",
                headers={"X-API-Key": "secret"},
                json=invalid,
            )

    assert unauthorized.status_code == incorrect.status_code == 401
    assert unauthorized.json() == incorrect.json()
    assert unauthorized.json()["error_code"] == "UNAUTHORIZED"
    assert malformed.status_code == 422
    assert malformed.json()["error_code"] == "VALIDATION_ERROR"
    assert assessment.calls == []


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("kind", "error", "error_code"),
    [
        (
            "apollon",
            ConversionError("secret input", original=ValueError()),
            "CONVERSION_ERROR",
        ),
        (
            "description",
            LlmRequestError("secret provider response"),
            "LLM_REQUEST_ERROR",
        ),
        (
            "apollon",
            LlmResponseError("secret provider response"),
            "LLM_RESPONSE_ERROR",
        ),
        (
            "description",
            RateLimitError("secret credentials"),
            "LLM_RATE_LIMIT_ERROR",
        ),
        (
            "apollon",
            ConfigError("secret configuration"),
            "CONFIG_ERROR",
        ),
        (
            "description",
            ReferenceNotAllowedError("secret diagram", original=ValueError()),
            "REFERENCE_NOT_ALLOWED",
        ),
        (
            "apollon",
            UseCaseError("secret failure", original=ValueError()),
            "USE_CASE_ERROR",
        ),
    ],
)
async def test_stream_reports_service_failure_as_terminal_error(
    kind: str, error: BaseAppException, error_code: str
) -> None:
    assessment = FailingAssessment(error)
    container = make_async_container(FakeProvider(assessment))
    app = create_app(
        settings=ApiSettings(API_SECRET="secret"), container=container
    )

    async with app.router.lifespan_context(app):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/v1/assessments/streams",
                headers={"X-API-Key": "secret"},
                json=_request(kind),
            )

    assert response.status_code == 200
    assert _events(response.text) == [
        ("progress", {"state": "extracting"}),
        (
            "error",
            {
                "ok": False,
                "error_code": error_code,
                "error_message": "The assessment could not be completed.",
            },
        ),
    ]
    assert "secret" not in response.text


@pytest.mark.anyio
async def test_stream_reports_unexpected_failure_as_terminal_error(
) -> None:
    assessment = FailingAssessment(RuntimeError("secret traceback"))
    container = make_async_container(FakeProvider(assessment))
    app = create_app(
        settings=ApiSettings(API_SECRET="secret"), container=container
    )

    async with app.router.lifespan_context(app):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/v1/assessments/streams",
                headers={"X-API-Key": "secret"},
                json=_request("description"),
            )

    assert response.status_code == 200
    assert _events(response.text)[-1] == (
        "error",
        {
            "ok": False,
            "error_code": "INTERNAL_ERROR",
            "error_message": "An internal error occurred.",
        },
    )
    assert "secret" not in response.text


@pytest.mark.anyio
async def test_result_projection_failure_is_a_terminal_internal_error() -> None:
    container = make_async_container(FakeProvider(InvalidResultAssessment()))
    app = create_app(
        settings=ApiSettings(API_SECRET="secret"), container=container
    )

    async with app.router.lifespan_context(app):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/v1/assessments/streams",
                headers={"X-API-Key": "secret"},
                json=_request("description"),
            )

    assert _events(response.text) == [
        (
            "error",
            {
                "ok": False,
                "error_code": "INTERNAL_ERROR",
                "error_message": "An internal error occurred.",
            },
        )
    ]


class BlockingUseCase:
    def __init__(self, result: object) -> None:
        self.result = result
        self.started = asyncio.Event()
        self.release = asyncio.Event()
        self.completed = False
        self.cancelled = False

    async def execute(self, _: object) -> object:
        self.started.set()
        try:
            await self.release.wait()
            self.completed = True
            return self.result
        except asyncio.CancelledError:
            self.cancelled = True
            raise


class FailingAfterStartUseCase:
    def __init__(self, started: asyncio.Event, error: Exception) -> None:
        self.started = started
        self.error = error

    async def execute(self, _: object) -> object:
        await self.started.wait()
        raise self.error


class FakeUseCase:
    def __init__(self, result: object) -> None:
        self.result = result
        self.calls = 0

    async def execute(self, _: object) -> object:
        self.calls += 1
        return self.result


class RecordingRepository:
    def __init__(self) -> None:
        self.diagrams: list[UseCaseDiagramPresentation] = []
        self.results: list[MetricsWithEvaluation] = []

    async def save_diagram_presentation(
        self, diagram: UseCaseDiagramPresentation
    ) -> None:
        self.diagrams.append(diagram)

    async def save_metrics(self, result: MetricsWithEvaluation) -> None:
        self.results.append(result)


class BlockingUnitOfWork:
    def __init__(self) -> None:
        self.commit_started = asyncio.Event()
        self.release_commit = asyncio.Event()
        self.commits = 0

    async def __aenter__(self) -> "BlockingUnitOfWork":
        return self

    async def __aexit__(self, *_: object) -> None:
        pass

    async def commit(self) -> None:
        self.commit_started.set()
        await self.release_commit.wait()
        self.commits += 1

    async def rollback(self) -> None:
        pass


class FailingUnitOfWork:
    def __init__(self) -> None:
        self.rollbacks = 0

    async def __aenter__(self) -> "FailingUnitOfWork":
        return self

    async def __aexit__(self, *args: object) -> None:
        if args[0] is not None:
            await self.rollback()

    async def commit(self) -> None:
        raise RuntimeError("secret database failure")

    async def rollback(self) -> None:
        self.rollbacks += 1


class LifecycleProvider(Provider):
    def __init__(self, assessment: DescriptionReferenceAssessment) -> None:
        super().__init__()
        self.assessment = assessment
        self.cleanups = 0

    @provide(scope=Scope.REQUEST)
    async def description_assessment(
        self,
    ) -> AsyncIterator[DescriptionReferenceAssessment]:
        yield self.assessment
        self.cleanups += 1

    @provide(scope=Scope.REQUEST)
    def apollon_assessment(self) -> ApollonReferenceAssessment:
        return cast(ApollonReferenceAssessment, self.assessment)


class AsgiStream:
    def __init__(self, app: Any, body: dict[str, Any]) -> None:
        self.app = app
        self.body = json.dumps(body).encode()
        self.messages: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        self.request_sent = False
        self.task: asyncio.Task[None] | None = None

    async def receive(self) -> dict[str, Any]:
        if not self.request_sent:
            self.request_sent = True
            return {
                "type": "http.request",
                "body": self.body,
                "more_body": False,
            }
        await asyncio.Event().wait()
        raise AssertionError("unreachable")

    async def send(self, message: dict[str, Any]) -> None:
        await self.messages.put(message)

    def start(self) -> None:
        scope = {
            "type": "http",
            "asgi": {"version": "3.0", "spec_version": "2.4"},
            "http_version": "1.1",
            "method": "POST",
            "scheme": "http",
            "path": "/v1/assessments/streams",
            "raw_path": b"/v1/assessments/streams",
            "query_string": b"",
            "root_path": "",
            "headers": [
                (b"host", b"test"),
                (b"content-type", b"application/json"),
                (b"x-api-key", b"secret"),
            ],
            "client": ("test", 123),
            "server": ("test", 80),
        }
        self.task = asyncio.create_task(
            self.app(scope, self.receive, self.send)
        )

    async def next(self) -> dict[str, Any]:
        async with asyncio.timeout(1):
            return await self.messages.get()


@pytest.mark.anyio
async def test_stream_delivers_incrementally_and_completes_after_commit() -> (
    None
):
    reference = UseCaseDiagramPresentation(
        nodes=[Node(uid="reference", name="Customer", type=NodeType.ACTOR)],
        relations=[],
    )
    candidate = UseCaseDiagramPresentation(
        nodes=[Node(uid="candidate", name="Customer", type=NodeType.ACTOR)],
        relations=[],
    )
    evaluation = EvaluationResult(
        node_evaluations=[
            NodeEvaluation(
                uid="candidate",
                syntactic_errors=[],
                rules_applied=[],
                naming_score=NamingUnderstandabilityScore.HIGH,
            )
        ],
        relation_evaluations=[],
        applied_rules=[],
    )
    matching = ExtendedMatching(
        reference=reference,
        candidate=candidate,
        node_matches=[
            NodeMatch(reference_uid="reference", candidate_uid="candidate")
        ],
        relation_matches=[],
    )
    description = BlockingUseCase(reference)
    matcher = BlockingUseCase(matching)
    evaluator = BlockingUseCase(evaluation)
    repository = RecordingRepository()
    unit_of_work = BlockingUnitOfWork()
    assessment = DescriptionReferenceAssessment(
        cast(DescriptionExtractor, description),
        cast(ApollonJsonExtractor, FakeUseCase(candidate)),
        cast(UseCaseDiagramMatcher, matcher),
        cast(PragmaticSyntacticLlmEvaluator, evaluator),
        cast(AssessmentWriteRepository, repository),
        cast(UnitOfWork, unit_of_work),
    )
    provider = LifecycleProvider(assessment)
    container = make_async_container(provider)
    app = create_app(
        settings=ApiSettings(API_SECRET="secret"), container=container
    )

    async with app.router.lifespan_context(app):
        stream = AsgiStream(app, _request("description"))
        stream.start()
        start = await stream.next()
        extracting = await stream.next()
        await description.started.wait()
        assert start["status"] == 200
        assert _events(extracting["body"].decode()) == [
            ("progress", {"state": "extracting"})
        ]
        assert provider.cleanups == 0

        description.release.set()
        analyzing = await stream.next()
        await matcher.started.wait()
        await evaluator.started.wait()
        assert _events(analyzing["body"].decode()) == [
            ("progress", {"state": "analyzing"})
        ]
        assert not matcher.completed
        assert not evaluator.completed

        matcher.release.set()
        evaluator.release.set()
        saving = await stream.next()
        await unit_of_work.commit_started.wait()
        assert _events(saving["body"].decode()) == [
            ("progress", {"state": "saving"})
        ]
        assert len(repository.diagrams) == 2
        assert len(repository.results) == 1
        assert provider.cleanups == 0

        unit_of_work.release_commit.set()
        result = await stream.next()
        end = await stream.next()
        assert _events(result["body"].decode())[0][0] == "result"
        assert _events(result["body"].decode())[0][1]["state"] == "completed"
        assert end["more_body"] is False
        assert stream.task is not None
        await stream.task
        assert unit_of_work.commits == 1
        assert provider.cleanups == 1


@pytest.mark.anyio
async def test_disallowed_candidate_streams_persisted_result_without_analysis() -> (
    None
):
    description = FakeUseCase(_diagram("reference"))
    candidate = FakeUseCase(UseCaseDiagramPresentation(nodes=[], relations=[]))
    matcher = FakeUseCase(None)
    evaluator = FakeUseCase(None)
    repository = RecordingRepository()
    unit_of_work = BlockingUnitOfWork()
    unit_of_work.release_commit.set()
    assessment = DescriptionReferenceAssessment(
        cast(DescriptionExtractor, description),
        cast(ApollonJsonExtractor, candidate),
        cast(UseCaseDiagramMatcher, matcher),
        cast(PragmaticSyntacticLlmEvaluator, evaluator),
        cast(AssessmentWriteRepository, repository),
        cast(UnitOfWork, unit_of_work),
    )
    provider = LifecycleProvider(assessment)
    container = make_async_container(provider)
    app = create_app(
        settings=ApiSettings(API_SECRET="secret"), container=container
    )

    async with app.router.lifespan_context(app):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/v1/assessments/streams",
                headers={"X-API-Key": "secret"},
                json=_request("description"),
            )

    events = _events(response.text)
    assert [event for event, _ in events] == [
        "progress",
        "progress",
        "progress",
        "result",
    ]
    assert events[-1][1]["data"]["candidate_is_allowed"] is False
    assert description.calls == candidate.calls == 1
    assert matcher.calls == evaluator.calls == 0
    assert len(repository.results) == 1
    assert unit_of_work.commits == 1
    assert provider.cleanups == 1


@pytest.mark.anyio
async def test_disallowed_reference_ends_stream_without_persistence() -> None:
    matcher = FakeUseCase(None)
    evaluator = FakeUseCase(None)
    repository = RecordingRepository()
    unit_of_work = BlockingUnitOfWork()
    assessment = DescriptionReferenceAssessment(
        cast(
            DescriptionExtractor,
            FakeUseCase(UseCaseDiagramPresentation(nodes=[], relations=[])),
        ),
        cast(ApollonJsonExtractor, FakeUseCase(_diagram("candidate"))),
        cast(UseCaseDiagramMatcher, matcher),
        cast(PragmaticSyntacticLlmEvaluator, evaluator),
        cast(AssessmentWriteRepository, repository),
        cast(UnitOfWork, unit_of_work),
    )
    container = make_async_container(LifecycleProvider(assessment))
    app = create_app(
        settings=ApiSettings(API_SECRET="secret"), container=container
    )

    async with app.router.lifespan_context(app):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/v1/assessments/streams",
                headers={"X-API-Key": "secret"},
                json=_request("description"),
            )

    events = _events(response.text)
    assert [event for event, _ in events] == ["progress", "progress", "error"]
    assert events[-1][1]["error_code"] == "REFERENCE_NOT_ALLOWED"
    assert matcher.calls == evaluator.calls == 0
    assert repository.diagrams == repository.results == []
    assert not unit_of_work.commit_started.is_set()


@pytest.mark.anyio
async def test_commit_failure_rolls_back_and_ends_stream_with_error() -> None:
    repository = RecordingRepository()
    unit_of_work = FailingUnitOfWork()
    assessment = DescriptionReferenceAssessment(
        cast(DescriptionExtractor, FakeUseCase(_diagram("reference"))),
        cast(
            ApollonJsonExtractor,
            FakeUseCase(UseCaseDiagramPresentation(nodes=[], relations=[])),
        ),
        cast(UseCaseDiagramMatcher, FakeUseCase(None)),
        cast(PragmaticSyntacticLlmEvaluator, FakeUseCase(None)),
        cast(AssessmentWriteRepository, repository),
        cast(UnitOfWork, unit_of_work),
    )
    provider = LifecycleProvider(assessment)
    container = make_async_container(provider)
    app = create_app(
        settings=ApiSettings(API_SECRET="secret"), container=container
    )

    async with app.router.lifespan_context(app):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/v1/assessments/streams",
                headers={"X-API-Key": "secret"},
                json=_request("description"),
            )

    events = _events(response.text)
    assert [event for event, _ in events] == [
        "progress",
        "progress",
        "progress",
        "error",
    ]
    assert events[-1][1]["error_code"] == "USE_CASE_ERROR"
    assert "secret" not in response.text
    assert unit_of_work.rollbacks == 1
    assert provider.cleanups == 1


@pytest.mark.anyio
async def test_analysis_failure_cancels_sibling_before_persistence() -> None:
    matcher = BlockingUseCase(None)
    evaluator = FailingAfterStartUseCase(
        matcher.started, LlmRequestError("secret provider response")
    )
    repository = RecordingRepository()
    unit_of_work = BlockingUnitOfWork()
    assessment = DescriptionReferenceAssessment(
        cast(DescriptionExtractor, FakeUseCase(_diagram("reference"))),
        cast(ApollonJsonExtractor, FakeUseCase(_diagram("candidate"))),
        cast(UseCaseDiagramMatcher, matcher),
        cast(PragmaticSyntacticLlmEvaluator, evaluator),
        cast(AssessmentWriteRepository, repository),
        cast(UnitOfWork, unit_of_work),
    )
    container = make_async_container(LifecycleProvider(assessment))
    app = create_app(
        settings=ApiSettings(API_SECRET="secret"), container=container
    )

    async with app.router.lifespan_context(app):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/v1/assessments/streams",
                headers={"X-API-Key": "secret"},
                json=_request("description"),
            )

    events = _events(response.text)
    assert [event for event, _ in events] == ["progress", "progress", "error"]
    assert events[-1][1]["error_code"] == "LLM_REQUEST_ERROR"
    assert matcher.cancelled
    assert repository.diagrams == repository.results == []
    assert not unit_of_work.commit_started.is_set()
