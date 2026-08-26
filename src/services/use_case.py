from collections.abc import Callable, Coroutine
from functools import wraps
from typing import Any, Protocol, TypeVar

from .exceptions import BaseAppException, UseCaseError

DataT = TypeVar("DataT", default=Any)
ResponseT = TypeVar("ResponseT", default=Any)


class UseCase[DataT, ResponseT](Protocol):
    async def execute(self, data: DataT) -> ResponseT: ...


def map_use_case_exceptions[**P, ResultT](
    operation: Callable[P, Coroutine[Any, Any, ResultT]],
) -> Callable[P, Coroutine[Any, Any, ResultT]]:
    @wraps(operation)
    async def wrapped(*args: P.args, **kwargs: P.kwargs) -> ResultT:
        try:
            return await operation(*args, **kwargs)
        except BaseAppException:
            raise
        except Exception as exc:
            raise UseCaseError(str(exc), original=exc) from exc

    return wrapped
