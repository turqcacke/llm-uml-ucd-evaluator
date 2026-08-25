from typing import Protocol, TypeVar

FromT = TypeVar("FromT")
ToT = TypeVar("ToT")


class BaseConverter[FromT, ToT](Protocol):
    def convert(self, from_value: FromT) -> ToT: ...
