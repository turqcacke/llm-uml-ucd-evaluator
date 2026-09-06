import threading

import pytest
from anyio import CapacityLimiter
from dishka import Provider, Scope, provide

from src.config import ApiSettings
from src.controller.api.app import create_app
from src.controller.di import make_api_container
from src.infrastructure.apollon import DomainToApollonConverter
from src.services.converter import ApollonLayoutConverter


class TrackingConverterProvider(Provider):
    def __init__(self, events: list[str]) -> None:
        super().__init__()
        self.events = events

    @provide(scope=Scope.APP, override=True)
    def converter(
        self,
        domain_converter: DomainToApollonConverter,
        limiter: CapacityLimiter,
    ) -> ApollonLayoutConverter:
        self.events.append("converter")
        return ApollonLayoutConverter(domain_converter, limiter)


@pytest.mark.anyio
async def test_lifespan_builds_converter_after_graphviz_probe(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[threading.Thread] = []
    events: list[str] = []
    container = make_api_container(
        TrackingConverterProvider(events),
        settings=ApiSettings(
            API_SECRET="secret", GRAPHVIZ_CONCURRENCY_LIMIT=2
        )
    )
    original_close = type(container).close
    close_calls = 0

    def version() -> tuple[int, ...]:
        calls.append(threading.current_thread())
        events.append("graphviz")
        return (14, 0, 0)

    async def close(target: object) -> None:
        nonlocal close_calls
        close_calls += 1
        await original_close(target)  # type: ignore[arg-type]

    monkeypatch.setattr("graphviz.version", version)
    monkeypatch.setattr(type(container), "close", close)
    app = create_app(container=container)

    async with app.router.lifespan_context(app):
        assert events == ["graphviz", "converter"]

    assert len(calls) == 1
    assert calls[0] is not threading.current_thread()
    assert close_calls == 1


@pytest.mark.anyio
async def test_lifespan_preserves_graphviz_failure_and_closes_container(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    diagnostic = RuntimeError("cannot parse dot output")
    calls = 0
    container = make_api_container(
        settings=ApiSettings(API_SECRET="secret")
    )
    original_close = type(container).close
    close_calls = 0

    def version() -> tuple[int, ...]:
        nonlocal calls
        calls += 1
        raise diagnostic

    async def close(target: object) -> None:
        nonlocal close_calls
        close_calls += 1
        await original_close(target)  # type: ignore[arg-type]

    monkeypatch.setattr("graphviz.version", version)
    monkeypatch.setattr(type(container), "close", close)
    app = create_app(container=container)

    with pytest.raises(RuntimeError) as raised:
        async with app.router.lifespan_context(app):
            pass

    assert raised.value is diagnostic
    assert calls == 1
    assert close_calls == 1
