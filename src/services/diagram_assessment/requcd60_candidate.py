from contextlib import aclosing
from dataclasses import dataclass

from src.model.domain import MetricsWithEvaluation
from src.model.requcd60.result import ReqUCD60Result
from src.services.evaluator import PragmaticSyntacticLlmEvaluator
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
class ReqUCD60CandidateAssessmentInput:
    reference_description: str
    candidate: ReqUCD60Result


class ReqUCD60CandidateAssessment(
    UseCase[ReqUCD60CandidateAssessmentInput, MetricsWithEvaluation]
):
    def __init__(
        self,
        candidate_extractor: ReqUCD60Extractor,
        description_extractor: DescriptionExtractor,
        matcher: UseCaseDiagramMatcher,
        evaluator: PragmaticSyntacticLlmEvaluator,
        repository: AssessmentWriteRepository,
        unit_of_work: UnitOfWork,
    ) -> None:
        self._candidate_extractor = candidate_extractor
        self._description_extractor = description_extractor
        self._dependencies = AssessmentDependencies(
            matcher, evaluator, repository, unit_of_work
        )

    @map_use_case_exceptions
    async def execute(
        self, data: ReqUCD60CandidateAssessmentInput
    ) -> MetricsWithEvaluation:
        reference = await self._description_extractor.execute(
            DescriptionExtractorInput(data.reference_description)
        )
        candidate = await self._candidate_extractor.execute(
            ReqUCD60ExtractorInput(data.candidate)
        )
        result = None
        async with aclosing(
            stream_assess_diagrams(reference, candidate, self._dependencies)
        ) as stream:
            async for _, result in stream:
                pass
        assert result is not None
        return result
