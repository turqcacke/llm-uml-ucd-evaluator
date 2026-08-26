from dataclasses import dataclass

from src.model.apollon import ApollonJson
from src.model.domain import MetricsWithEvaluation
from src.services.evaluator import PragmaticSyntacticLlmEvaluator
from src.services.extractor import (
    ApollonJsonExtractor,
    ApollonJsonExtractorInput,
    DescriptionExtractor,
    DescriptionExtractorInput,
)
from src.services.matcher import UseCaseDiagramMatcher
from src.services.ports import UnitOfWork
from src.services.use_case import UseCase, map_use_case_exceptions

from .assessment import assess_diagrams
from .repository import AssessmentWriteRepository


@dataclass(frozen=True)
class DescriptionReferenceAssessmentInput:
    reference_description: str
    candidate: ApollonJson


class DescriptionReferenceAssessment(
    UseCase[DescriptionReferenceAssessmentInput, MetricsWithEvaluation]
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
        self._matcher = matcher
        self._evaluator = evaluator
        self._repository = repository
        self._unit_of_work = unit_of_work

    @map_use_case_exceptions
    async def execute(
        self, data: DescriptionReferenceAssessmentInput
    ) -> MetricsWithEvaluation:
        reference = await self._description_extractor.execute(
            DescriptionExtractorInput(data.reference_description)
        )
        candidate = await self._candidate_extractor.execute(
            ApollonJsonExtractorInput(data.candidate)
        )
        return await assess_diagrams(
            reference,
            candidate,
            self._matcher,
            self._evaluator,
            self._repository,
            self._unit_of_work,
        )
