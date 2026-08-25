from asyncio import Event
from decimal import Decimal
from typing import Any, cast

import pytest

from src.model.apollon import ApollonJson
from src.model.domain import (
    EvaluationResult,
    ExtendedMatching,
    Node,
    NodeType,
    UseCaseDiagramPresentation,
)
from src.model.domain.evaluation import (
    NamingUnderstandabilityScore,
    NodeEvaluation,
)
from src.model.domain.matching import NodeMatch
from src.services.exceptions.llm_client import LlmRequestError
from src.services.exceptions.pipelines import PipelineError
from src.services.pipelines.diagram_assessment import (
    ApollonReferenceAssessment,
    ApollonReferenceAssessmentInput,
    DescriptionReferenceAssessment,
    DescriptionReferenceAssessmentInput,
)
from src.services.pipelines.evaluator import PragmaticSyntacticLlmEvaluator
from src.services.pipelines.extractor.apollon_json import ApollonJsonExtractor
from src.services.pipelines.extractor.text import DescriptionExtractor
from src.services.pipelines.matcher.use_case_diagram import (
    UseCaseDiagramMatcher,
)


class FakePipeline:
    def __init__(self, result: Any) -> None:
        self.result = result
        self.calls: list[Any] = []

    async def execute(self, data: Any) -> Any:
        self.calls.append(data)
        return self.result


class SequencePipeline:
    def __init__(self, *results: Any) -> None:
        self.results = iter(results)
        self.calls: list[Any] = []

    async def execute(self, data: Any) -> Any:
        self.calls.append(data)
        result = next(self.results)
        if isinstance(result, Exception):
            raise result
        return result


class BlockingPipeline:
    def __init__(self) -> None:
        self.started = Event()
        self.cancelled = Event()

    async def execute(self, data: Any) -> Any:
        self.started.set()
        try:
            await Event().wait()
        finally:
            self.cancelled.set()


class FailingAfterStartPipeline:
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
        nodes=[Node(id=node_id, name="Customer", type=NodeType.ACTOR)],
        relations=[],
    )


@pytest.mark.anyio
async def test_description_reference_assessment_returns_metrics_and_evaluation(
) -> None:
    reference = _diagram("reference")
    candidate = _diagram("candidate")
    evaluation = EvaluationResult(
        node_evaluations=[
            NodeEvaluation(
                id="candidate",
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
            NodeMatch(reference_id="reference", candidate_id="candidate")
        ],
        relation_matches=[],
    )
    description_extractor = FakePipeline(reference)
    candidate_extractor = FakePipeline(candidate)
    matcher = FakePipeline(matching)
    evaluator = FakePipeline(evaluation)
    assessment = DescriptionReferenceAssessment(
        cast(DescriptionExtractor, description_extractor),
        cast(ApollonJsonExtractor, candidate_extractor),
        cast(UseCaseDiagramMatcher, matcher),
        cast(PragmaticSyntacticLlmEvaluator, evaluator),
    )

    result = await assessment.execute(
        DescriptionReferenceAssessmentInput(
            reference_description="A customer uses the system.",
            candidate=_apollon(),
        )
    )

    assert result.model_dump() == {
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
        "evaluation": evaluation.model_dump(),
    }


@pytest.mark.anyio
async def test_disallowed_candidate_returns_fixed_metrics_without_analysis(
) -> None:
    reference = _diagram("reference")
    candidate = UseCaseDiagramPresentation(nodes=[], relations=[])
    description_extractor = FakePipeline(reference)
    candidate_extractor = FakePipeline(candidate)
    matcher = FakePipeline(None)
    evaluator = FakePipeline(None)
    assessment = DescriptionReferenceAssessment(
        cast(DescriptionExtractor, description_extractor),
        cast(ApollonJsonExtractor, candidate_extractor),
        cast(UseCaseDiagramMatcher, matcher),
        cast(PragmaticSyntacticLlmEvaluator, evaluator),
    )

    result = await assessment.execute(
        DescriptionReferenceAssessmentInput("Reference", _apollon())
    )

    assert result.candidate_is_allowed is False
    assert result.completeness_rate == Decimal(0)
    assert result.redundancy_rate == Decimal(1)
    assert result.syntactic_error_rate == Decimal(1)
    assert result.evaluation is None
    assert matcher.calls == []
    assert evaluator.calls == []


@pytest.mark.anyio
async def test_disallowed_reference_fails_without_analysis() -> None:
    reference = UseCaseDiagramPresentation(nodes=[], relations=[])
    candidate = _diagram("candidate")
    matcher = FakePipeline(None)
    evaluator = FakePipeline(None)
    assessment = DescriptionReferenceAssessment(
        cast(DescriptionExtractor, FakePipeline(reference)),
        cast(ApollonJsonExtractor, FakePipeline(candidate)),
        cast(UseCaseDiagramMatcher, matcher),
        cast(PragmaticSyntacticLlmEvaluator, evaluator),
    )

    with pytest.raises(PipelineError, match="Reference diagram"):
        await assessment.execute(
            DescriptionReferenceAssessmentInput("Reference", _apollon())
        )

    assert matcher.calls == []
    assert evaluator.calls == []


@pytest.mark.anyio
async def test_apollon_reference_assessment_extracts_both_diagrams() -> None:
    reference = _diagram("reference")
    candidate = _diagram("candidate")
    extraction = SequencePipeline(reference, candidate)
    evaluation = EvaluationResult(
        node_evaluations=[
            NodeEvaluation(
                id="candidate",
                syntactic_errors=[],
                rules_applied=[],
                naming_score=NamingUnderstandabilityScore.MEDIUM,
            )
        ],
        relation_evaluations=[],
        applied_rules=[],
    )
    matching = ExtendedMatching(
        reference=reference,
        candidate=candidate,
        node_matches=[
            NodeMatch(reference_id="reference", candidate_id="candidate")
        ],
        relation_matches=[],
    )
    assessment = ApollonReferenceAssessment(
        cast(ApollonJsonExtractor, extraction),
        cast(UseCaseDiagramMatcher, FakePipeline(matching)),
        cast(PragmaticSyntacticLlmEvaluator, FakePipeline(evaluation)),
    )
    reference_source = _apollon()
    candidate_source = _apollon()

    result = await assessment.execute(
        ApollonReferenceAssessmentInput(reference_source, candidate_source)
    )

    assert result.semantic_f1_score == Decimal(1)
    assert result.evaluation == evaluation
    assert [call.apollon_model for call in extraction.calls] == [
        reference_source,
        candidate_source,
    ]


@pytest.mark.anyio
async def test_analysis_failure_cancels_the_other_task() -> None:
    matcher = BlockingPipeline()
    evaluator = FailingAfterStartPipeline(matcher.started)
    assessment = DescriptionReferenceAssessment(
        cast(DescriptionExtractor, FakePipeline(_diagram("reference"))),
        cast(ApollonJsonExtractor, FakePipeline(_diagram("candidate"))),
        cast(UseCaseDiagramMatcher, matcher),
        cast(PragmaticSyntacticLlmEvaluator, evaluator),
    )

    with pytest.raises(PipelineError) as error_info:
        await assessment.execute(
            DescriptionReferenceAssessmentInput("Reference", _apollon())
        )

    assert matcher.cancelled.is_set()
    assert isinstance(error_info.value.original, BaseExceptionGroup)


@pytest.mark.anyio
async def test_analysis_reraises_single_application_error() -> None:
    matcher = BlockingPipeline()
    error = LlmRequestError("Provider rejected the request")
    evaluator = FailingAfterStartPipeline(matcher.started, error)
    assessment = DescriptionReferenceAssessment(
        cast(DescriptionExtractor, FakePipeline(_diagram("reference"))),
        cast(ApollonJsonExtractor, FakePipeline(_diagram("candidate"))),
        cast(UseCaseDiagramMatcher, matcher),
        cast(PragmaticSyntacticLlmEvaluator, evaluator),
    )

    with pytest.raises(LlmRequestError) as error_info:
        await assessment.execute(
            DescriptionReferenceAssessmentInput("Reference", _apollon())
        )

    assert matcher.cancelled.is_set()
    assert error_info.value is error


@pytest.mark.anyio
async def test_apollon_reference_assessment_maps_extraction_failure() -> None:
    error = RuntimeError("Candidate extraction failed")
    matcher = FakePipeline(None)
    evaluator = FakePipeline(None)
    assessment = ApollonReferenceAssessment(
        cast(
            ApollonJsonExtractor,
            SequencePipeline(_diagram("reference"), error),
        ),
        cast(UseCaseDiagramMatcher, matcher),
        cast(PragmaticSyntacticLlmEvaluator, evaluator),
    )

    with pytest.raises(
        PipelineError, match="Candidate extraction failed"
    ) as info:
        await assessment.execute(
            ApollonReferenceAssessmentInput(_apollon(), _apollon())
        )

    assert info.value.original is error
    assert matcher.calls == []
    assert evaluator.calls == []
