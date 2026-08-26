from enum import StrEnum
from typing import Protocol, TypeVar

from pydantic import BaseModel

TResponse = TypeVar("TResponse", bound=BaseModel)


class LLMRoles(StrEnum):
    USER = "user"
    ASSITANT = "assistant"
    SYSTEM = "system"


class ChatModel[TResponse](Protocol):
    async def invoke(self, prompt: str, role: LLMRoles) -> TResponse: ...
