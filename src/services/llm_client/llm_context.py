import copy
from typing import Protocol

from langchain.messages import (
    AIMessage,
    AnyMessage,
    HumanMessage,
    SystemMessage,
)

from src.model.llm.context import (
    LlmMessage,
    LLMRoles,
    SystemContext,
    UserContext,
)


class ContextBuilder(Protocol):
    def add(self, element: LlmMessage | AnyMessage) -> None: ...
    def build_context(self) -> list[AnyMessage]: ...


class SimpleContextBuilder(ContextBuilder):
    _PATTERN = """\
# System instructions

{system_prompt}{guardrails_section}"""
    _GUARDRAILS_PATTERN = """

# Guardrails

{guardrails}"""

    def __init__(self, guardrails: list[str], system_prompt: str):
        self._system_context = SystemContext(system_prompt, guardrails)
        self._user_context = UserContext([])

    def add(self, element: LlmMessage | AnyMessage) -> None:
        if isinstance(element, LlmMessage):
            match element.role:
                case LLMRoles.SYSTEM:
                    element = SystemMessage(content=element.content)
                case LLMRoles.ASSITANT:
                    element = AIMessage(content=element.content)
                case _:
                    element = HumanMessage(content=element.content)
        self._user_context.messages.append(element)

    def build_context(self) -> list[AnyMessage]:
        guardrails = self._system_context.guardrails
        guardrails_section = ""
        if guardrails:
            guardrails_section = self._GUARDRAILS_PATTERN.format(
                guardrails="\n".join(f"- {rule}" for rule in guardrails)
            )
        system_prompt = self._PATTERN.format(
            system_prompt=self._system_context.system_prompt.strip(),
            guardrails_section=guardrails_section,
        )
        user_messages = copy.copy(self._user_context.messages)
        self._user_context.messages.clear()
        return [SystemMessage(content=system_prompt)] + user_messages
