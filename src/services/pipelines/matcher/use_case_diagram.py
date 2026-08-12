from dataclasses import dataclass

from src.model.domain.diagram_presentation import UseCaseDiagramPresentation
from src.model.domain.evaluation import MatchingResult
from src.model.llm.context import LLMRoles
from src.services.llm_client import ChatModel

from ..base import BasePipeline

_MESSAGE_PROMPT = """
Reference:
{reference}
\n\n
Candidate:
{candidate}
"""


@dataclass(frozen=True)
class UseCaseDiagramMatcherInput:
    reference: UseCaseDiagramPresentation
    candidate: UseCaseDiagramPresentation


class UseCaseDiagramMatcher(
    BasePipeline[UseCaseDiagramMatcherInput, MatchingResult]
):
    def __init__(
        self,
        chat_model: ChatModel[MatchingResult],
    ):
        self._chat_model = chat_model

    async def execute(
        self, data: UseCaseDiagramMatcherInput
    ) -> MatchingResult:
        return await self._chat_model.invoke(
            _MESSAGE_PROMPT.format(
                reference=data.reference.model_dump_json(),
                candidate=data.candidate.model_dump_json(),
            ),
            LLMRoles.USER,
        )
