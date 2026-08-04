from dataclasses import dataclass
from enum import StrEnum
from typing import NamedTuple

from langchain.messages import AnyMessage


class LLMRoles(StrEnum):
    USER = "user"
    ASSITANT = "assistant"
    SYSTEM = "system"


class LlmMessage(NamedTuple):
    role: LLMRoles
    content: str


@dataclass(frozen=True)
class SystemContext:
    system_prompt: str
    guardrails: list[str]


@dataclass(frozen=True)
class UserContext:
    messages: list[AnyMessage]
