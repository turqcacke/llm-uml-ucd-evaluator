from dataclasses import dataclass

from src.app_logging import logger
from src.model.apollon import ApollonJson
from src.model.domain.diagram_presentation import UseCaseDiagramPresentation
from src.model.llm.context import LLMRoles

from ..base import BasePipeline
from .dependencies import ApollonExtractorChatModel

_MESSAGE_PROMPT = """
{json_model}
"""


@dataclass
class ApollonLlmExtractorInput:
    apollon_model: ApollonJson


class ApollonLlmExtractor(
    BasePipeline[ApollonLlmExtractorInput, UseCaseDiagramPresentation]
):
    def __init__(
        self,
        chat_model: ApollonExtractorChatModel,
    ):
        self._chat_model = chat_model

    async def execute(
        self, data: ApollonLlmExtractorInput
    ) -> UseCaseDiagramPresentation:
        json_model = data.apollon_model.model_dump_json()
        logger.info(
            "Apollon extraction started characters={}", len(json_model)
        )
        result = await self._chat_model.invoke(
            _MESSAGE_PROMPT.format(json_model=json_model),
            LLMRoles.USER,
        )
        logger.info(
            "Apollon extraction completed nodes={} relations={}",
            len(result.nodes),
            len(result.relations),
        )
        return result
