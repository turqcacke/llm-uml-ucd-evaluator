from dataclasses import dataclass

from src.model.apollon import ApollonJson
from src.model.domain.diagram_presentation import UseCaseDiagramPresentation
from src.model.llm.context import LLMRoles

from ..base import BasePipeline
from .dependencies import ApollonExtractorChatModel

_MESSAGE_PROMPT = """
{json_model}
"""


@dataclass
class ApollonExtratorInput:
    appolon_model: ApollonJson


class ApollonExtractor(
    BasePipeline[ApollonExtratorInput, UseCaseDiagramPresentation]
):
    def __init__(
        self,
        chat_model: ApollonExtractorChatModel,
    ):
        self._chat_model = chat_model

    async def execute(
        self, data: ApollonExtratorInput
    ) -> UseCaseDiagramPresentation:
        return await self._chat_model.invoke(
            _MESSAGE_PROMPT.format(
                json_model=data.appolon_model.model_dump_json()
            ),
            LLMRoles.USER,
        )
