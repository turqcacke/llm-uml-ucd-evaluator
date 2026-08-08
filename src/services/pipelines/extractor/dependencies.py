from typing import Annotated

from dishka import FromComponent

from src.model.domain.diagram_presentation import UseCaseDiagramPresentation
from src.services.llm_client import ChatModel

type TextExtractorChatModel = Annotated[
    ChatModel[UseCaseDiagramPresentation], FromComponent("text")
]
type ApollonExtractorChatModel = Annotated[
    ChatModel[UseCaseDiagramPresentation], FromComponent("apollon")
]
