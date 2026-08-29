from enum import StrEnum
from typing import Any, AsyncGenerator, Protocol, TypeVar

from pydantic import BaseModel

TResponse = TypeVar("TResponse", bound=BaseModel)
SResponse = TypeVar("SResponse", default=Any)


class LLMRoles(StrEnum):
    USER = "user"
    ASSITANT = "assistant"
    SYSTEM = "system"


class ChatModel[TResponse](Protocol):
    async def invoke(self, prompt: str, role: LLMRoles) -> TResponse: ...


class ChatModelStream[SResponse](Protocol):
    async def stream(
        self, prompt: str, role: LLMRoles
    ) -> AsyncGenerator[SResponse, None]: ...
