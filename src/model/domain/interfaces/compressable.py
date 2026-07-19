from typing import NamedTuple, Protocol


class CompressableResult(NamedTuple):
    pattern: str
    value: str


class Compressable(Protocol):
    def compress(self) -> str:
        """Returns compressed `str` object representation"""
        ...

    def pattern(self) -> str:
        """Returns `compress()` function follows"""
        ...
