from typing import Any, Protocol, TypeVar

DataT = TypeVar("DataT", default=Any)
ResponseT = TypeVar("ResponseT", default=Any)


class BasePipeline[DataT, ResponseT](Protocol):
    async def execute(self, data: DataT) -> ResponseT: ...
