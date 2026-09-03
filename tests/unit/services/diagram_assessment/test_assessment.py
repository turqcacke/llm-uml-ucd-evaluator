import json
from asyncio import Event
from decimal import Decimal
from typing import Any, cast

import pytest

from src.model.apollon import ApollonJson
from src.model.domain import (
    AssessmentState,
    ExtendedMatching,
    Node,
    NodeType,
    PragmaticEvaluationResult,
    UseCaseDiagramPresentation,
)
from src.model.domain.evaluation import (
    NamingUnderstandabilityScore,
    NodeNamingEvaluation,
)
from src.model.domain.exceptions import MetricsCalculationError
from src.model.domain.matching import NodeMatch
from src.services.diagram_assessment import (
    ApollonToApollonAssessment,
    ApollonToApollonAssessmentInput,
    DescriptionReferenceAssessment,
    DescriptionReferenceAssessmentInput,
)
from src.services.evaluator import (
    PragmaticLlmEvaluator,
    SyntacticDiagramEvaluator,
)
from src.services.exceptions import (
    ConversionError,
    LlmRequestError,
    LlmResponseError,
    ReferenceNotAllowedError,
    UseCaseError,
)
from src.services.extractor import ApollonJsonExtractor, DescriptionExtractor
from src.services.matcher import UseCaseDiagramMatcher
from src.services.ports import LLMRoles


class FakeUseCase:
    def __init__(self, result: Any) -> None:
        self.result = result
        self.calls: list[Any] = []

    async def execute(self, data: Any) -> Any:
        self.calls.append(data)
        return self.result


class FakeRepository:
    def __init__(self) -> None:
        self.diagrams: list[UseCaseDiagramPresentation] = []
        self.results: list[Any] = []

    async def save_diagram_presentation(
        self, data: UseCaseDiagramPresentation
    ) -> None:
        self.diagrams.append(data)

    async def save_metrics(self, data: Any) -> None:
        self.results.append(data)


class FakeUnitOfWork:
    def __init__(self, commit_error: Exception | None = None) -> None:
        self.commit_error = commit_error
        self.commits = 0
        self.rollbacks = 0

    async def __aenter__(self) -> "FakeUnitOfWork":
        return self

    async def __aexit__(self, *args: object) -> None:
        if args[0] is not None:
            await self.rollback()

    async def commit(self) -> None:
        if self.commit_error:
            raise self.commit_error
        self.commits += 1

    async def rollback(self) -> None:
        self.rollbacks += 1


class SequenceUseCase:
    def __init__(self, *results: Any) -> None:
        self.results = iter(results)
        self.calls: list[Any] = []

    async def execute(self, data: Any) -> Any:
        self.calls.append(data)
        result = next(self.results)
        if isinstance(result, Exception):
            raise result
        return result


class BlockingUseCase:
    def __init__(self) -> None:
        self.started = Event()
        self.cancelled = Event()

    async def execute(self, data: Any) -> Any:
        self.started.set()
        try:
            await Event().wait()
        finally:
            self.cancelled.set()


class FailingAfterStartUseCase:
    def __init__(self, started: Event, error: Exception | None = None) -> None:
        self.started = started
        self.error = error or RuntimeError("Evaluation failed")

    async def execute(self, data: Any) -> Any:
        await self.started.wait()
        raise self.error


def _apollon() -> ApollonJson:
    return ApollonJson.model_validate(
        {"model": {"elements": {}, "relationships": {}}}
    )


def _diagram(node_id: str) -> UseCaseDiagramPresentation:
    return UseCaseDiagramPresentation(
        nodes=[Node(uid=node_id, name="Customer", type=NodeType.ACTOR)],
        relations=[],
    )


@pytest.mark.anyio
async def test_description_reference_assessment_returns_metrics_and_evaluation() -> (
    None
):
    reference = _diagram("reference")
    candidate = _diagram("candidate")
    evaluation = PragmaticEvaluationResult(
        nodes=[
            NodeNamingEvaluation(
                uid="candidate",
                score=NamingUnderstandabilityScore.HIGH,
            )
        ],
    )
    matching = ExtendedMatching(
        reference=reference,
        candidate=candidate,
        node_matches=[
            NodeMatch(reference_uid="reference", candidate_uid="candidate")
        ],
        relation_matches=[],
    )
    description_extractor = FakeUseCase(reference)
    candidate_extractor = FakeUseCase(candidate)
    matcher = FakeUseCase(matching)

    class NamingModel:
        async def invoke(
            self, prompt: str, role: LLMRoles
        ) -> PragmaticEvaluationResult:
            context = json.loads(
                prompt.split("<input>", 1)[1].split("</input>", 1)[0]
            )
            assert context["description"] == "A customer uses the system."
            return evaluation

    evaluator = PragmaticLlmEvaluator(NamingModel())
    repository = FakeRepository()
    unit_of_work = FakeUnitOfWork()
    assessment = DescriptionReferenceAssessment(
        cast(DescriptionExtractor, description_extractor),
        cast(ApollonJsonExtractor, candidate_extractor),
        cast(UseCaseDiagramMatcher, matcher),
        evaluator,
        repository,
        unit_of_work,
        syntactic_evaluator=SyntacticDiagramEvaluator(),
    )

    result = await assessment.execute(
        DescriptionReferenceAssessmentInput(
            reference_description="A customer uses the system.",
            candidate=_apollon(),
        )
    )

    assert result.model_dump(exclude={"uid"}) == {
        "candidate_is_allowed": True,
        "redundancy_rate": Decimal(0),
        "completeness_rate": Decimal(1),
        "semantic_precision": Decimal(1),
        "semantic_f1_score": Decimal(1),
        "syntactic_error_rate": Decimal(0),
        "naming_understandability_score": Decimal(3),
        "reference_complexity": Decimal(0),
        "candidate_complexity": Decimal(0),
        "complexity_difference": Decimal(0),
        "complexity_deviation_rate": Decimal(0),
        "evaluation": {
            "syntactic": {
                "nodes": [
                    {
                        "uid": "candidate",
                        "checks": {
                            "name_present": True,
                            "parent_exists": True,
                        },
                    }
                ],
                "relations": [],
            },
            "pragmatic": evaluation.model_dump(),
        },
        "reference_uid": reference.uid,
        "candidate_uid": candidate.uid,
        "matching": {
            "node_matches": [
                {
                    "reference_uid": "reference",
                    "candidate_uid": "candidate",
                }
            ],
            "relation_matches": [],
            "missing_nodes": [],
            "redundant_nodes": [],
            "missing_relations": [],
            "redundant_relations": [],
        },
    }
    assert result.uid
    assert result.reference == reference
    assert repository.diagrams == [reference, candidate]
    assert result.matching == matching
    assert repository.results == [result]
    assert unit_of_work.commits == 1


@pytest.mark.anyio
async def test_assessment_stream_yields_each_stage_and_final_result() -> None:
    reference = _diagram("reference")
    candidate = UseCaseDiagramPresentation(nodes=[], relations=[])
    repository = FakeRepository()
    unit_of_work = FakeUnitOfWork()
    assessment = DescriptionReferenceAssessment(
        cast(DescriptionExtractor, FakeUseCase(reference)),
        cast(ApollonJsonExtractor, FakeUseCase(candidate)),
        cast(UseCaseDiagramMatcher, FakeUseCase(None)),
        cast(PragmaticLlmEvaluator, FakeUseCase(None)),
        repository,
        unit_of_work,
        syntactic_evaluator=SyntacticDiagramEvaluator(),
    )

    progress = [
        item
        async for item in assessment.stream(
            DescriptionReferenceAssessmentInput("Reference", _apollon())
        )
    ]

    assert [state for state, _ in progress] == [
        AssessmentState.EXTRACTING,
        AssessmentState.ANALYZING,
        AssessmentState.SAVING,
        AssessmentState.COMPLETED,
    ]
    assert [result for _, result in progress[:-1]] == [None, None, None]
    assert progress[-1][1] is repository.results[0]
    assert unit_of_work.commits == 1


@pytest.mark.anyio
async def test_disallowed_candidate_returns_fixed_metrics_without_analysis() -> (
    None
):
    reference = _diagram("reference")
    candidate = UseCaseDiagramPresentation(nodes=[], relations=[])
    description_extractor = FakeUseCase(reference)
    candidate_extractor = FakeUseCase(candidate)
    matcher = FakeUseCase(None)
    evaluator = FakeUseCase(None)
    repository = FakeRepository()
    unit_of_work = FakeUnitOfWork()
    assessment = DescriptionReferenceAssessment(
        cast(DescriptionExtractor, description_extractor),
        cast(ApollonJsonExtractor, candidate_extractor),
        cast(UseCaseDiagramMatcher, matcher),
        cast(PragmaticLlmEvaluator, evaluator),
        repository,
        unit_of_work,
        syntactic_evaluator=SyntacticDiagramEvaluator(),
    )

    result = await assessment.execute(
        DescriptionReferenceAssessmentInput("Reference", _apollon())
    )

    assert result.candidate_is_allowed is False
    assert result.completeness_rate == Decimal(0)
    assert result.redundancy_rate == Decimal(1)
    assert result.syntactic_error_rate == Decimal(1)
    assert result.evaluation is None
    assert result.reference == reference
    assert repository.diagrams == [reference, candidate]
    assert result.matching is None
    assert repository.results == [result]
    assert unit_of_work.commits == 1
    assert matcher.calls == []
    assert evaluator.calls == []


@pytest.mark.anyio
async def test_disallowed_reference_fails_without_analysis() -> None:
    reference = UseCaseDiagramPresentation(nodes=[], relations=[])
    candidate = _diagram("candidate")
    matcher = FakeUseCase(None)
    evaluator = FakeUseCase(None)
    repository = FakeRepository()
    unit_of_work = FakeUnitOfWork()
    assessment = DescriptionReferenceAssessment(
        cast(DescriptionExtractor, FakeUseCase(reference)),
        cast(ApollonJsonExtractor, FakeUseCase(candidate)),
        cast(UseCaseDiagramMatcher, matcher),
        cast(PragmaticLlmEvaluator, evaluator),
        repository,
        unit_of_work,
        syntactic_evaluator=SyntacticDiagramEvaluator(),
    )

    with pytest.raises(
        ReferenceNotAllowedError, match="Reference diagram"
    ) as error_info:
        await assessment.execute(
            DescriptionReferenceAssessmentInput("Reference", _apollon())
        )

    assert isinstance(error_info.value.original, MetricsCalculationError)
    assert matcher.calls == []
    assert evaluator.calls == []
    assert repository.diagrams == []
    assert unit_of_work.commits == 0


@pytest.mark.anyio
async def test_repeated_assessments_return_distinct_result_uids() -> None:
    reference = _diagram("reference")
    candidate = UseCaseDiagramPresentation(nodes=[], relations=[])
    repository = FakeRepository()
    unit_of_work = FakeUnitOfWork()
    assessment = DescriptionReferenceAssessment(
        cast(DescriptionExtractor, FakeUseCase(reference)),
        cast(ApollonJsonExtractor, FakeUseCase(candidate)),
        cast(UseCaseDiagramMatcher, FakeUseCase(None)),
        cast(PragmaticLlmEvaluator, FakeUseCase(None)),
        repository,
        unit_of_work,
        syntactic_evaluator=SyntacticDiagramEvaluator(),
    )

    first = await assessment.execute(
        DescriptionReferenceAssessmentInput("Reference", _apollon())
    )
    second = await assessment.execute(
        DescriptionReferenceAssessmentInput("Reference", _apollon())
    )

    assert first.uid != second.uid
    assert [result.uid for result in repository.results] == [
        first.uid,
        second.uid,
    ]


@pytest.mark.anyio
async def test_storage_failure_fails_execution_and_rolls_back() -> None:
    repository = FakeRepository()
    unit_of_work = FakeUnitOfWork(RuntimeError("Commit failed"))
    assessment = DescriptionReferenceAssessment(
        cast(DescriptionExtractor, FakeUseCase(_diagram("reference"))),
        cast(
            ApollonJsonExtractor,
            FakeUseCase(UseCaseDiagramPresentation(nodes=[], relations=[])),
        ),
        cast(UseCaseDiagramMatcher, FakeUseCase(None)),
        cast(PragmaticLlmEvaluator, FakeUseCase(None)),
        repository,
        unit_of_work,
        syntactic_evaluator=SyntacticDiagramEvaluator(),
    )

    with pytest.raises(UseCaseError, match="Commit failed"):
        await assessment.execute(
            DescriptionReferenceAssessmentInput("Reference", _apollon())
        )

    assert unit_of_work.rollbacks == 1


@pytest.mark.anyio
async def test_apollon_to_apollon_assessment_extracts_both_diagrams() -> None:
    reference = _diagram("reference")
    candidate = _diagram("candidate")
    extraction = SequenceUseCase(reference, candidate)
    evaluation = PragmaticEvaluationResult(
        nodes=[
            NodeNamingEvaluation(
                uid="candidate",
                score=NamingUnderstandabilityScore.MEDIUM,
            )
        ],
    )
    matching = ExtendedMatching(
        reference=reference,
        candidate=candidate,
        node_matches=[
            NodeMatch(reference_uid="reference", candidate_uid="candidate")
        ],
        relation_matches=[],
    )
    assessment = ApollonToApollonAssessment(
        cast(ApollonJsonExtractor, extraction),
        cast(UseCaseDiagramMatcher, FakeUseCase(matching)),
        cast(PragmaticLlmEvaluator, FakeUseCase(evaluation)),
        FakeRepository(),
        FakeUnitOfWork(),
        syntactic_evaluator=SyntacticDiagramEvaluator(),
    )
    reference_source = _apollon()
    candidate_source = _apollon()

    result = await assessment.execute(
        ApollonToApollonAssessmentInput(reference_source, candidate_source)
    )

    assert result.semantic_f1_score == Decimal(1)
    assert result.evaluation is not None
    assert result.evaluation.pragmatic == evaluation
    assert [call.apollon_model for call in extraction.calls] == [
        reference_source,
        candidate_source,
    ]


@pytest.mark.anyio
async def test_analysis_failure_cancels_the_other_task() -> None:
    matcher = BlockingUseCase()
    evaluator = FailingAfterStartUseCase(matcher.started)
    assessment = DescriptionReferenceAssessment(
        cast(DescriptionExtractor, FakeUseCase(_diagram("reference"))),
        cast(ApollonJsonExtractor, FakeUseCase(_diagram("candidate"))),
        cast(UseCaseDiagramMatcher, matcher),
        cast(PragmaticLlmEvaluator, evaluator),
        FakeRepository(),
        FakeUnitOfWork(),
        syntactic_evaluator=SyntacticDiagramEvaluator(),
    )

    with pytest.raises(UseCaseError) as error_info:
        await assessment.execute(
            DescriptionReferenceAssessmentInput("Reference", _apollon())
        )

    assert matcher.cancelled.is_set()
    assert isinstance(error_info.value.original, BaseExceptionGroup)


@pytest.mark.anyio
async def test_analysis_reraises_single_application_error() -> None:
    matcher = BlockingUseCase()
    error = LlmRequestError("Provider rejected the request")
    evaluator = FailingAfterStartUseCase(matcher.started, error)
    assessment = DescriptionReferenceAssessment(
        cast(DescriptionExtractor, FakeUseCase(_diagram("reference"))),
        cast(ApollonJsonExtractor, FakeUseCase(_diagram("candidate"))),
        cast(UseCaseDiagramMatcher, matcher),
        cast(PragmaticLlmEvaluator, evaluator),
        FakeRepository(),
        FakeUnitOfWork(),
        syntactic_evaluator=SyntacticDiagramEvaluator(),
    )

    with pytest.raises(LlmRequestError) as error_info:
        await assessment.execute(
            DescriptionReferenceAssessmentInput("Reference", _apollon())
        )

    assert matcher.cancelled.is_set()
    assert error_info.value is error


@pytest.mark.anyio
async def test_invalid_evaluation_is_reported_as_llm_response_error() -> None:
    reference = _diagram("reference")
    candidate = _diagram("candidate")
    matching = ExtendedMatching(
        reference=reference,
        candidate=candidate,
        node_matches=[],
        relation_matches=[],
    )

    class IncompleteNamingModel:
        async def invoke(
            self, prompt: str, role: LLMRoles
        ) -> PragmaticEvaluationResult:
            return PragmaticEvaluationResult(nodes=[])

    repository = FakeRepository()
    assessment = DescriptionReferenceAssessment(
        cast(DescriptionExtractor, FakeUseCase(reference)),
        cast(ApollonJsonExtractor, FakeUseCase(candidate)),
        cast(UseCaseDiagramMatcher, FakeUseCase(matching)),
        PragmaticLlmEvaluator(IncompleteNamingModel()),
        repository,
        FakeUnitOfWork(),
        syntactic_evaluator=SyntacticDiagramEvaluator(),
    )

    with pytest.raises(LlmResponseError, match="exactly one"):
        await assessment.execute(
            DescriptionReferenceAssessmentInput("Reference", _apollon())
        )

    assert repository.results == []


@pytest.mark.anyio
async def test_apollon_to_apollon_assessment_maps_extraction_failure() -> None:
    error = RuntimeError("Candidate extraction failed")
    matcher = FakeUseCase(None)
    evaluator = FakeUseCase(None)
    assessment = ApollonToApollonAssessment(
        cast(
            ApollonJsonExtractor,
            SequenceUseCase(_diagram("reference"), error),
        ),
        cast(UseCaseDiagramMatcher, matcher),
        cast(PragmaticLlmEvaluator, evaluator),
        FakeRepository(),
        FakeUnitOfWork(),
        syntactic_evaluator=SyntacticDiagramEvaluator(),
    )

    with pytest.raises(
        UseCaseError, match="Candidate extraction failed"
    ) as info:
        await assessment.execute(
            ApollonToApollonAssessmentInput(_apollon(), _apollon())
        )

    assert info.value.original is error
    assert matcher.calls == []
    assert evaluator.calls == []


@pytest.mark.anyio
async def test_apollon_to_apollon_assessment_preserves_conversion_error() -> (
    None
):
    original = ValueError("Duplicate node UID")
    error = ConversionError("Invalid Apollon diagram", original=original)
    assessment = ApollonToApollonAssessment(
        cast(ApollonJsonExtractor, SequenceUseCase(error)),
        cast(UseCaseDiagramMatcher, FakeUseCase(None)),
        cast(PragmaticLlmEvaluator, FakeUseCase(None)),
        FakeRepository(),
        FakeUnitOfWork(),
        syntactic_evaluator=SyntacticDiagramEvaluator(),
    )

    with pytest.raises(ConversionError) as error_info:
        await assessment.execute(
            ApollonToApollonAssessmentInput(_apollon(), _apollon())
        )

    assert error_info.value is error
    assert error_info.value.original is original


@pytest.mark.anyio
async def test_deterministic_evaluation_failure_is_execution_error():
    error = RuntimeError("Syntax execution failed")
    repository = FakeRepository()
    assessment = DescriptionReferenceAssessment(
        cast(DescriptionExtractor, FakeUseCase(_diagram("reference"))),
        cast(ApollonJsonExtractor, FakeUseCase(_diagram("candidate"))),
        cast(UseCaseDiagramMatcher, FakeUseCase(None)),
        cast(PragmaticLlmEvaluator, FakeUseCase(None)),
        repository,
        FakeUnitOfWork(),
        syntactic_evaluator=cast(
            SyntacticDiagramEvaluator, SequenceUseCase(error)
        ),
    )
    with pytest.raises(
        UseCaseError, match="Syntax execution failed"
    ) as raised:
        await assessment.execute(
            DescriptionReferenceAssessmentInput("Reference", _apollon())
        )
    assert raised.value.original is error
    assert repository.diagrams == repository.results == []
