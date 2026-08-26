from dataclasses import dataclass

from src.app_logging import logger
from src.model.apollon import ApollonJson
from src.model.domain.diagram_presentation import UseCaseDiagramPresentation
from src.services.ports import ChatModel, LLMRoles
from src.services.shared.prompts import EXTRACTOR_FROM_APOLLON_MODEL_REQUEST
from src.services.use_case import UseCase, map_use_case_exceptions


@dataclass
class ApollonLlmExtractorInput:
    apollon_model: ApollonJson


class ApollonLlmExtractor(
    UseCase[ApollonLlmExtractorInput, UseCaseDiagramPresentation]
):
    def __init__(
        self,
        chat_model: ChatModel[UseCaseDiagramPresentation],
    ):
        self._chat_model = chat_model

    @map_use_case_exceptions
    async def execute(
        self, data: ApollonLlmExtractorInput
    ) -> UseCaseDiagramPresentation:
        json_model = data.apollon_model.model_dump_json()
        logger.info(
            "Apollon extraction started characters={}", len(json_model)
        )
        result = await self._chat_model.invoke(
            EXTRACTOR_FROM_APOLLON_MODEL_REQUEST.format(
                json_model=json_model
            ),
            LLMRoles.USER,
        )
        logger.info(
            "Apollon extraction completed nodes={} relations={}",
            len(result.nodes),
            len(result.relations),
        )
        return result
