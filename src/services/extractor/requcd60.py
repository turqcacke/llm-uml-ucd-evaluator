from dataclasses import dataclass

from src.model.domain import UseCaseDiagramPresentation
from src.model.requcd60.result import ReqUCD60Result
from src.services.use_case import UseCase, map_use_case_exceptions

from .converter import BaseConverter


@dataclass(frozen=True)
class ReqUCD60ExtractorInput:
    reference: ReqUCD60Result


class ReqUCD60Extractor(
    UseCase[ReqUCD60ExtractorInput, UseCaseDiagramPresentation]
):
    def __init__(
        self,
        converter: BaseConverter[ReqUCD60Result, UseCaseDiagramPresentation],
    ) -> None:
        self._converter = converter

    @map_use_case_exceptions
    async def execute(
        self, data: ReqUCD60ExtractorInput
    ) -> UseCaseDiagramPresentation:
        return self._converter.convert(data.reference)
