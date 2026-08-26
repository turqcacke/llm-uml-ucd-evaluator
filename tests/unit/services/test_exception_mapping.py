from collections.abc import Awaitable, Callable
from typing import Never

import pytest

from src.model.apollon import ApollonJson
from src.model.domain import UseCaseDiagramPresentation
from src.services.exceptions import UseCaseError
from src.services.extractor import (
    ApollonJsonExtractor,
    ApollonJsonExtractorInput,
    ApollonLlmExtractor,
    ApollonLlmExtractorInput,
    DescriptionExtractor,
    DescriptionExtractorInput,
)
from src.services.matcher import (
    UseCaseDiagramMatcher,
    UseCaseDiagramMatcherInput,
)
from src.services.ports import LLMRoles


class FailingChatModel:
    def __init__(self, error: Exception) -> None:
        self.error = error

    async def invoke(self, prompt: str, role: LLMRoles) -> Never:
        raise self.error


class FailingConverter:
    def __init__(self, error: Exception) -> None:
        self.error = error

    def convert(self, from_value: ApollonJson) -> Never:
        raise self.error


def _apollon_json() -> ApollonJson:
    return ApollonJson.model_validate(
        {"model": {"elements": {}, "relationships": {}}}
    )


def _diagram() -> UseCaseDiagramPresentation:
    return UseCaseDiagramPresentation(nodes=[], relations=[])


async def _run_apollon_json(error: Exception) -> object:
    return await ApollonJsonExtractor(FailingConverter(error)).execute(
        ApollonJsonExtractorInput(_apollon_json())
    )


async def _run_apollon_llm(error: Exception) -> object:
    return await ApollonLlmExtractor(FailingChatModel(error)).execute(
        ApollonLlmExtractorInput(_apollon_json())
    )


async def _run_description(error: Exception) -> object:
    return await DescriptionExtractor(FailingChatModel(error)).execute(
        DescriptionExtractorInput("A customer places an order.")
    )


async def _run_matcher(error: Exception) -> object:
    diagram = _diagram()
    return await UseCaseDiagramMatcher(FailingChatModel(error)).execute(
        UseCaseDiagramMatcherInput(reference=diagram, candidate=diagram)
    )


@pytest.mark.anyio
@pytest.mark.parametrize(
    "execute_use_case",
    [
        _run_apollon_json,
        _run_apollon_llm,
        _run_description,
        _run_matcher,
    ],
)
async def test_use_case_maps_unexpected_exception(
    execute_use_case: Callable[[Exception], Awaitable[object]],
) -> None:
    error = RuntimeError("Unexpected dependency failure")

    with pytest.raises(UseCaseError, match=str(error)) as error_info:
        await execute_use_case(error)

    assert error_info.value.original is error
