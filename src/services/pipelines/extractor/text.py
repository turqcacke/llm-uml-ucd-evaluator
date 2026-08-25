from dataclasses import dataclass

from src.app_logging import logger
from src.model.domain.diagram_presentation import UseCaseDiagramPresentation
from src.model.llm.context import LLMRoles
from src.services.shared.prompts import EXTRACTOR_FROM_DESCRIPTION_REQUEST

from ..base import BasePipeline, map_pipeline_exceptions
from .dependencies import TextExtractorChatModel


@dataclass(frozen=True)
class DesciptionExtractorInput:
    description_prompt: str


class DescriptionExtractor(
    BasePipeline[DesciptionExtractorInput, UseCaseDiagramPresentation]
):
    def __init__(
        self,
        chat_model: TextExtractorChatModel,
    ):
        self._chat_model = chat_model

    @map_pipeline_exceptions
    async def execute(
        self, data: DesciptionExtractorInput
    ) -> UseCaseDiagramPresentation:
        logger.info(
            "Description extraction started characters={}",
            len(data.description_prompt),
        )
        result = await self._chat_model.invoke(
            EXTRACTOR_FROM_DESCRIPTION_REQUEST.format(
                description_prompt=data.description_prompt.strip()
            ).strip(),
            LLMRoles.USER,
        )
        logger.info(
            "Description extraction completed nodes={} relations={}",
            len(result.nodes),
            len(result.relations),
        )
        return result
