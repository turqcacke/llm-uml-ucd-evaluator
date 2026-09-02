from contextlib import aclosing
from dataclasses import dataclass

from src.model.domain import MetricsWithEvaluation
from src.model.requcd60.result import ReqUCD60Result
from src.services.evaluator import (
    PragmaticLlmEvaluator,
    SyntacticDiagramEvaluator,
)
from src.services.extractor import (
    DescriptionExtractor,
    DescriptionExtractorInput,
)
from src.services.extractor.requcd60 import (
    ReqUCD60Extractor,
    ReqUCD60ExtractorInput,
)
from src.services.matcher import UseCaseDiagramMatcher
from src.services.ports import UnitOfWork
from src.services.use_case import UseCase, map_use_case_exceptions

from .assessment import AssessmentDependencies, stream_assess_diagrams
from .repository import AssessmentWriteRepository


@dataclass(frozen=True)
class ReqUCD60ReferenceAssessmentInput:
    reference: ReqUCD60Result
    candidate_description: str


class ReqUCD60ReferenceAssessment(
    UseCase[ReqUCD60ReferenceAssessmentInput, MetricsWithEvaluation]
):
    def __init__(
        self,
        reference_extractor: ReqUCD60Extractor,
        description_extractor: DescriptionExtractor,
        matcher: UseCaseDiagramMatcher,
        pragmatic_evaluator: PragmaticLlmEvaluator,
        repository: AssessmentWriteRepository,
        unit_of_work: UnitOfWork,
        syntactic_evaluator: SyntacticDiagramEvaluator,
    ) -> None:
        self._reference_extractor = reference_extractor
        self._description_extractor = description_extractor
        self._dependencies = AssessmentDependencies(
            matcher,
            pragmatic_evaluator,
            repository,
            unit_of_work,
            syntactic_evaluator,
        )

    @map_use_case_exceptions
    async def execute(
        self, data: ReqUCD60ReferenceAssessmentInput
    ) -> MetricsWithEvaluation:
        reference = await self._reference_extractor.execute(
            ReqUCD60ExtractorInput(data.reference)
        )
        candidate = await self._description_extractor.execute(
            DescriptionExtractorInput(data.candidate_description)
        )
        result = None
        async with aclosing(
            stream_assess_diagrams(
                reference,
                candidate,
                self._dependencies,
                description=data.candidate_description,
            )
        ) as stream:
            async for _, result in stream:
                pass
        assert result is not None
        return result
