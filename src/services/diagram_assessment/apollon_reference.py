from collections.abc import AsyncGenerator
from dataclasses import dataclass

from src.model.apollon import ApollonJson
from src.model.domain import AssessmentState, MetricsWithEvaluation
from src.services.evaluator import PragmaticSyntacticLlmEvaluator
from src.services.extractor import (
    ApollonJsonExtractor,
    ApollonJsonExtractorInput,
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
class ApollonReferenceAssessmentInput:
    reference: ApollonJson
    candidate: ApollonJson


class ApollonReferenceAssessment(
    UseCase[ApollonReferenceAssessmentInput, MetricsWithEvaluation],
    StreamingUseCase[ApollonReferenceAssessmentInput, AssessmentProgress],
):
    def __init__(
        self,
        extractor: ApollonJsonExtractor,
        matcher: UseCaseDiagramMatcher,
        evaluator: PragmaticSyntacticLlmEvaluator,
        repository: AssessmentWriteRepository,
        unit_of_work: UnitOfWork,
    ) -> None:
        self._extractor = extractor
        self._dependencies = AssessmentDependencies(
            matcher,
            evaluator,
            repository,
            unit_of_work,
        )

    async def execute(
        self, data: ApollonReferenceAssessmentInput
    ) -> MetricsWithEvaluation:
        result = None
        async for _, result in self.stream(data):
            pass
        assert result is not None
        return result

    async def stream(
        self, data: ApollonReferenceAssessmentInput
    ) -> AsyncGenerator[AssessmentProgress]:
        async for progress in map_stream_exceptions(self._stream(data)):
            yield progress

    async def _stream(
        self, data: ApollonReferenceAssessmentInput
    ) -> AsyncGenerator[AssessmentProgress]:
        yield AssessmentState.EXTRACTING, None
        reference = await self._extractor.execute(
            ApollonJsonExtractorInput(data.reference)
        )
        candidate = await self._extractor.execute(
            ApollonJsonExtractorInput(data.candidate)
        )
        async for progress in stream_assess_diagrams(
            reference,
            candidate,
            self._dependencies,
        ):
            yield progress
