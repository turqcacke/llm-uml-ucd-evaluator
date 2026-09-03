from collections.abc import Awaitable, Callable
from typing import Never

import pytest

from src.model.apollon import ApollonJson
from src.model.domain import UseCaseDiagramPresentation
from src.services.exceptions import (
    BaseAppException,
    ConfigError,
    ConversionError,
    LlmRequestError,
    LlmResponseError,
    RateLimitError,
    ReferenceNotAllowedError,
    UseCaseError,
)
from src.services.extractor import (
    ApollonJsonExtractor,
    ApollonJsonExtractorInput,
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


@pytest.mark.parametrize(
    ("exception", "error_code"),
    [
        (ConversionError("Invalid input", original=ValueError()), "CONVERSION_ERROR"),
        (
            ReferenceNotAllowedError(
                "Reference diagram is not allowed", original=ValueError()
            ),
            "REFERENCE_NOT_ALLOWED",
        ),
        (LlmRequestError("Request failed"), "LLM_REQUEST_ERROR"),
        (LlmResponseError("Response failed"), "LLM_RESPONSE_ERROR"),
        (RateLimitError("Rate limited"), "LLM_RATE_LIMIT_ERROR"),
        (ConfigError("Invalid config"), "CONFIG_ERROR"),
        (UseCaseError("Execution failed", original=ValueError()), "USE_CASE_ERROR"),
    ],
)
def test_service_exceptions_expose_stable_error_codes(
    exception: BaseAppException, error_code: str
) -> None:
    assert exception.error_code == error_code


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
