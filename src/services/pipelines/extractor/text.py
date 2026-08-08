from dataclasses import dataclass

from src.model.domain.diagram_presentation import UseCaseDiagramPresentation
from src.model.llm.context import LLMRoles

from ..base import BasePipeline
from .dependencies import TextExtractorChatModel

_MESSAGE_PROMPT = """
{description_prompt}
"""


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

    async def execute(
        self, data: DesciptionExtractorInput
    ) -> UseCaseDiagramPresentation:
        return await self._chat_model.invoke(
            _MESSAGE_PROMPT.format(description_prompt=data.description_prompt),
            LLMRoles.USER,
        )
