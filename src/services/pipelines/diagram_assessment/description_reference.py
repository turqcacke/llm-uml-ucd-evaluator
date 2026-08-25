from dataclasses import dataclass

from src.model.apollon import ApollonJson
from src.model.domain import MetricsWithEvaluation

from ..base import BasePipeline, map_pipeline_exceptions
from ..evaluator import PragmaticSyntacticLlmEvaluator
from ..extractor.apollon_json import (
    ApollonJsonExtractor,
    ApollonJsonExtractorInput,
)
from ..extractor.text import DesciptionExtractorInput, DescriptionExtractor
from ..matcher.use_case_diagram import UseCaseDiagramMatcher
from .common import assess


@dataclass(frozen=True)
class DescriptionReferenceAssessmentInput:
    reference_description: str
    candidate: ApollonJson


class DescriptionReferenceAssessment(
    BasePipeline[DescriptionReferenceAssessmentInput, MetricsWithEvaluation]
):
    def __init__(
        self,
        description_extractor: DescriptionExtractor,
        candidate_extractor: ApollonJsonExtractor,
        matcher: UseCaseDiagramMatcher,
        evaluator: PragmaticSyntacticLlmEvaluator,
    ) -> None:
        self._description_extractor = description_extractor
        self._candidate_extractor = candidate_extractor
        self._matcher = matcher
        self._evaluator = evaluator

    @map_pipeline_exceptions
    async def execute(
        self, data: DescriptionReferenceAssessmentInput
    ) -> MetricsWithEvaluation:
        reference = await self._description_extractor.execute(
            DesciptionExtractorInput(data.reference_description)
        )
        candidate = await self._candidate_extractor.execute(
            ApollonJsonExtractorInput(data.candidate)
        )
        return await assess(
            reference,
            candidate,
            self._matcher,
            self._evaluator,
        )
