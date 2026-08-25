from dataclasses import dataclass

from src.app_logging import logger
from src.model.apollon import ApollonJson
from src.model.domain import UseCaseDiagramPresentation
from src.services.converters.base import BaseConverter
from src.services.pipelines.base import BasePipeline, map_pipeline_exceptions


@dataclass
class ApollonJsonExtractorInput:
    apollon_model: ApollonJson


class ApollonJsonExtractor(
    BasePipeline[ApollonJsonExtractorInput, UseCaseDiagramPresentation]
):
    def __init__(
        self, converter: BaseConverter[ApollonJson, UseCaseDiagramPresentation]
    ):
        self._converter = converter

    @map_pipeline_exceptions
    async def execute(
        self, data: ApollonJsonExtractorInput
    ) -> UseCaseDiagramPresentation:
        logger.info(
            "Apollon Json extraction started object={}",
            data.apollon_model,
        )
        result = self._converter.convert(data.apollon_model)
        logger.info(
            "Apollon extraction completed nodes={} relations={}",
            len(result.nodes),
            len(result.relations),
        )
        return result
