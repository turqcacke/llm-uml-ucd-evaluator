from dataclasses import dataclass

from src.app_logging import logger
from src.model.domain.diagram_presentation import UseCaseDiagramPresentation
from src.services.ports import ChatModel, LLMRoles
from src.services.shared.prompts import EXTRACTOR_FROM_DESCRIPTION_REQUEST
from src.services.use_case import UseCase, map_use_case_exceptions


@dataclass(frozen=True)
class DescriptionExtractorInput:
    description_prompt: str


class DescriptionExtractor(
    UseCase[DescriptionExtractorInput, UseCaseDiagramPresentation]
):
    def __init__(
        self,
        chat_model: ChatModel[UseCaseDiagramPresentation],
    ):
        self._chat_model = chat_model

    @map_use_case_exceptions
    async def execute(
        self, data: DescriptionExtractorInput
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
