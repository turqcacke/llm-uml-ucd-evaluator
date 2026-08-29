from collections.abc import AsyncGenerator
from dataclasses import dataclass

from src.model.apollon import ApollonJson
from src.model.domain import AssessmentState, MetricsWithEvaluation
from src.services.evaluator import PragmaticSyntacticLlmEvaluator
from src.services.extractor import (
    ApollonJsonExtractor,
    ApollonJsonExtractorInput,
    DescriptionExtractor,
    DescriptionExtractorInput,
)
from src.services.matcher import UseCaseDiagramMatcher
from src.services.ports import UnitOfWork
from src.services.use_case import (
    StreamingUseCase,
    UseCase,
    map_stream_exceptions,
)

from .assessment import (
    AssessmentDependencies,
    AssessmentProgress,
    stream_assess_diagrams,
)
from .repository import AssessmentWriteRepository


@dataclass(frozen=True)
class DescriptionReferenceAssessmentInput:
    reference_description: str
    candidate: ApollonJson


class DescriptionReferenceAssessment(
    UseCase[DescriptionReferenceAssessmentInput, MetricsWithEvaluation],
    StreamingUseCase[DescriptionReferenceAssessmentInput, AssessmentProgress],
):
    def __init__(
        self,
        description_extractor: DescriptionExtractor,
        candidate_extractor: ApollonJsonExtractor,
        matcher: UseCaseDiagramMatcher,
        evaluator: PragmaticSyntacticLlmEvaluator,
        repository: AssessmentWriteRepository,
        unit_of_work: UnitOfWork,
    ) -> None:
        self._description_extractor = description_extractor
        self._candidate_extractor = candidate_extractor
        self._dependencies = AssessmentDependencies(
            matcher,
            evaluator,
            repository,
            unit_of_work,
        )

    async def execute(
        self, data: DescriptionReferenceAssessmentInput
    ) -> MetricsWithEvaluation:
        result = None
        async for _, result in self.stream(data):
            pass
        assert result is not None
        return result

    async def stream(
        self, data: DescriptionReferenceAssessmentInput
    ) -> AsyncGenerator[AssessmentProgress]:
        async for progress in map_stream_exceptions(self._stream(data)):
            yield progress

    async def _stream(
        self, data: DescriptionReferenceAssessmentInput
    ) -> AsyncGenerator[AssessmentProgress]:
        yield AssessmentState.EXTRACTING, None
        reference = await self._description_extractor.execute(
            DescriptionExtractorInput(data.reference_description)
        )
        candidate = await self._candidate_extractor.execute(
            ApollonJsonExtractorInput(data.candidate)
        )
        async for progress in stream_assess_diagrams(
            reference,
            candidate,
            self._dependencies,
        ):
            yield progress
