from dataclasses import dataclass

from src.app_logging import logger
from src.model.domain.diagram_presentation import UseCaseDiagramPresentation
from src.model.domain.matching import ExtendedMatching, MinMatching
from src.model.llm.context import LLMRoles
from src.services.llm_client import ChatModel
from src.services.shared.prompts import USE_CASE_DIAGRAM_MATCHER_REQUEST

from ..base import BasePipeline, map_pipeline_exceptions


@dataclass(frozen=True)
class UseCaseDiagramMatcherInput:
    reference: UseCaseDiagramPresentation
    candidate: UseCaseDiagramPresentation


class UseCaseDiagramMatcher(
    BasePipeline[UseCaseDiagramMatcherInput, ExtendedMatching]
):
    def __init__(
        self,
        chat_model: ChatModel[MinMatching],
    ):
        self._chat_model = chat_model

    @map_pipeline_exceptions
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
        result = ExtendedMatching(
            node_matches=llm_result.node_matches,
            relation_matches=llm_result.relation_matches,
            reference=data.reference,
            candidate=data.candidate,
        )
        logger.info(
            "Diagram matching completed node_matches={} relation_matches={} "
            "missing_nodes={} redundant_nodes={}",
            len(result.node_matches),
            len(result.relation_matches),
            len(result.missing_nodes),
            len(result.redundant_nodes),
        )
        return result
