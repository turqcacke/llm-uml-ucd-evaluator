import threading

import anyio
import pytest

from src.model.apollon import ApollonLayout
from src.model.domain import UseCaseDiagramPresentation
from src.services.converter import (
    ApollonLayoutConverter,
    ApollonLayoutConverterInput,
    BaseConverter,
)
from src.services.exceptions import ConversionError, UseCaseError


def _diagram() -> UseCaseDiagramPresentation:
    return UseCaseDiagramPresentation(nodes=[], relations=[])


class _Converter(
    BaseConverter[UseCaseDiagramPresentation, ApollonLayout]
):
    def __init__(self, result: ApollonLayout | Exception):
        self.result = result

    def convert(
        self, from_value: UseCaseDiagramPresentation
    ) -> ApollonLayout:
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


@pytest.mark.anyio
async def test_apollon_layout_converter_returns_layout() -> None:
    expected = ApollonLayout()
    converter = ApollonLayoutConverter(
        _Converter(expected), anyio.CapacityLimiter(1)
    )

    result = await converter.execute(ApollonLayoutConverterInput(_diagram()))

    assert result is expected


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (
            ConversionError("invalid diagram", original=ValueError()),
            ConversionError,
        ),
        (RuntimeError("converter failed"), UseCaseError),
    ],
)
async def test_apollon_layout_converter_maps_failures(
    error: Exception, expected: type[Exception]
) -> None:
    converter = ApollonLayoutConverter(
        _Converter(error), anyio.CapacityLimiter(1)
    )

    with pytest.raises(expected, match=str(error)) as raised:
        await converter.execute(ApollonLayoutConverterInput(_diagram()))

    if isinstance(raised.value, UseCaseError):
        assert raised.value.original is error
    else:
        assert raised.value is error


class _BlockingConverter(
    BaseConverter[UseCaseDiagramPresentation, ApollonLayout]
):
    def __init__(self, expected_active: int):
        self.expected_active = expected_active
        self.active = 0
        self.maximum_active = 0
        self.expected_reached = threading.Event()
        self.release = threading.Event()
        self.lock = threading.Lock()

    def convert(
        self, from_value: UseCaseDiagramPresentation
    ) -> ApollonLayout:
        with self.lock:
            self.active += 1
            self.maximum_active = max(self.maximum_active, self.active)
            if self.active == self.expected_active:
                self.expected_reached.set()
        if not self.release.wait(1):
            raise TimeoutError("test conversion was not released")
        with self.lock:
            self.active -= 1
        return ApollonLayout()


@pytest.mark.anyio
async def test_apollon_layout_converter_bounds_active_work() -> None:
    dependency = _BlockingConverter(expected_active=2)
    converter = ApollonLayoutConverter(
        dependency, anyio.CapacityLimiter(2)
    )

    async with anyio.create_task_group() as tasks:
        for _ in range(6):
            tasks.start_soon(
                converter.execute, ApollonLayoutConverterInput(_diagram())
            )
        reached = await anyio.to_thread.run_sync(
            dependency.expected_reached.wait, 1
        )
        assert reached
        dependency.release.set()

    assert dependency.maximum_active == 2


@pytest.mark.anyio
async def test_cancellation_keeps_capacity_until_conversion_finishes() -> None:
    dependency = _BlockingConverter(expected_active=1)
    converter = ApollonLayoutConverter(
        dependency, anyio.CapacityLimiter(1)
    )
    first_scope = anyio.CancelScope()

    async def run_first() -> None:
        with first_scope:
            await converter.execute(ApollonLayoutConverterInput(_diagram()))

    async with anyio.create_task_group() as tasks:
        tasks.start_soon(run_first)
        reached = await anyio.to_thread.run_sync(
            dependency.expected_reached.wait, 1
        )
        assert reached
        first_scope.cancel()
        tasks.start_soon(
            converter.execute, ApollonLayoutConverterInput(_diagram())
        )
        await anyio.sleep(0.05)
        assert dependency.maximum_active == 1
        dependency.release.set()

    assert dependency.maximum_active == 1
