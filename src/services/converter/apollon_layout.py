from dataclasses import dataclass

from anyio import CapacityLimiter, to_thread

from src.model.apollon import ApollonLayout
from src.model.domain import UseCaseDiagramPresentation
from src.services.use_case import UseCase, map_use_case_exceptions

from .base import BaseConverter


@dataclass(frozen=True)
class ApollonLayoutConverterInput:
    diagram: UseCaseDiagramPresentation


class ApollonLayoutConverter(
    UseCase[ApollonLayoutConverterInput, ApollonLayout]
):
    def __init__(
        self,
        converter: BaseConverter[UseCaseDiagramPresentation, ApollonLayout],
        limiter: CapacityLimiter,
    ) -> None:
        self._converter = converter
        self._limiter = limiter

    @map_use_case_exceptions
    async def execute(
        self, data: ApollonLayoutConverterInput
    ) -> ApollonLayout:
        return await to_thread.run_sync(
            self._converter.convert,
            data.diagram,
            abandon_on_cancel=False,
            limiter=self._limiter,
        )
