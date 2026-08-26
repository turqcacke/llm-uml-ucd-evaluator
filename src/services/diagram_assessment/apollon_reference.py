from dataclasses import dataclass

from src.model.apollon import ApollonJson
from src.model.domain import MetricsWithEvaluation
from src.services.evaluator import PragmaticSyntacticLlmEvaluator
from src.services.extractor import (
    ApollonJsonExtractor,
    ApollonJsonExtractorInput,
)
from src.services.matcher import UseCaseDiagramMatcher
from src.services.use_case import UseCase, map_use_case_exceptions

from .assessment import assess_diagrams


@dataclass(frozen=True)
class ApollonReferenceAssessmentInput:
    reference: ApollonJson
    candidate: ApollonJson


class ApollonReferenceAssessment(
    UseCase[ApollonReferenceAssessmentInput, MetricsWithEvaluation]
):
    def __init__(
        self,
        extractor: ApollonJsonExtractor,
        matcher: UseCaseDiagramMatcher,
        evaluator: PragmaticSyntacticLlmEvaluator,
    ) -> None:
        self._extractor = extractor
        self._matcher = matcher
        self._evaluator = evaluator

    @map_use_case_exceptions
    async def execute(
        self, data: ApollonReferenceAssessmentInput
    ) -> MetricsWithEvaluation:
        reference = await self._extractor.execute(
            ApollonJsonExtractorInput(data.reference)
        )
        candidate = await self._extractor.execute(
            ApollonJsonExtractorInput(data.candidate)
        )
        return await assess_diagrams(
            reference,
            candidate,
            self._matcher,
            self._evaluator,
        )
