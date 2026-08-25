from dataclasses import dataclass

from src.model.apollon import ApollonJson
from src.model.domain import MetricsWithEvaluation

from ..base import BasePipeline, map_pipeline_exceptions
from ..evaluator import PragmaticSyntacticLlmEvaluator
from ..extractor.apollon_json import (
    ApollonJsonExtractor,
    ApollonJsonExtractorInput,
)
from ..matcher.use_case_diagram import UseCaseDiagramMatcher
from .common import assess


@dataclass(frozen=True)
class ApollonReferenceAssessmentInput:
    reference: ApollonJson
    candidate: ApollonJson


class ApollonReferenceAssessment(
    BasePipeline[ApollonReferenceAssessmentInput, MetricsWithEvaluation]
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

    @map_pipeline_exceptions
    async def execute(
        self, data: ApollonReferenceAssessmentInput
    ) -> MetricsWithEvaluation:
        reference = await self._extractor.execute(
            ApollonJsonExtractorInput(data.reference)
        )
        candidate = await self._extractor.execute(
            ApollonJsonExtractorInput(data.candidate)
        )
        return await assess(
            reference,
            candidate,
            self._matcher,
            self._evaluator,
        )
