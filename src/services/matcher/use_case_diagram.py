from dataclasses import dataclass

from src.app_logging import logger
from src.model.domain.diagram_presentation import UseCaseDiagramPresentation
from src.model.domain.exceptions import MatchingError
from src.model.domain.matching import ExtendedMatching, MinMatching
from src.services.exceptions import LlmResponseError
from src.services.ports import ChatModel, LLMRoles
from src.services.shared.prompts import USE_CASE_DIAGRAM_MATCHER_REQUEST
from src.services.use_case import UseCase, map_use_case_exceptions


@dataclass(frozen=True)
class UseCaseDiagramMatcherInput:
    reference: UseCaseDiagramPresentation
    candidate: UseCaseDiagramPresentation


class UseCaseDiagramMatcher(
    UseCase[UseCaseDiagramMatcherInput, ExtendedMatching]
):
    def __init__(
        self,
        chat_model: ChatModel[MinMatching],
    ):
        self._chat_model = chat_model

    @map_use_case_exceptions
    async def execute(
        self, data: UseCaseDiagramMatcherInput
    ) -> ExtendedMatching:
        logger.info(
            "Diagram matching started reference_nodes={} candidate_nodes={}",
            len(data.reference.nodes),
            len(data.candidate.nodes),
        )
        llm_result = await self._chat_model.invoke(
            USE_CASE_DIAGRAM_MATCHER_REQUEST.format(
                reference=data.reference.model_dump_json(),
                candidate=data.candidate.model_dump_json(),
            ),
            LLMRoles.USER,
        )
        try:
            result = ExtendedMatching(
                node_matches=llm_result.node_matches,
                relation_matches=llm_result.relation_matches,
                reference=data.reference,
                candidate=data.candidate,
            )
        except MatchingError as exc:
            raise LlmResponseError(str(exc), original=exc) from exc
        logger.info(
            "Diagram matching completed node_matches={} relation_matches={} "
            "missing_nodes={} redundant_nodes={}",
            len(result.node_matches),
            len(result.relation_matches),
            len(result.missing_nodes),
            len(result.redundant_nodes),
        )
        return result
