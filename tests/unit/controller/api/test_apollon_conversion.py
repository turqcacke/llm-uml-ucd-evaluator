from typing import cast

import pytest
from dishka import Provider, Scope, provide
from httpx import ASGITransport, AsyncClient

from src.config import ApiSettings
from src.controller.api.app import create_app
from src.controller.di import make_api_container
from src.model.apollon import (
    ApollonLayout,
    ApollonLayoutBounds,
    ApollonLayoutDirection,
    ApollonLayoutEndpoint,
    ApollonLayoutNode,
    ApollonLayoutPoint,
    ApollonLayoutRelation,
    ApollonLayoutSize,
    ApollonNodeType,
    ApollonRelationType,
)
from src.services.converter import (
    ApollonLayoutConverter,
    ApollonLayoutConverterInput,
)
from src.services.exceptions import (
    BaseAppException,
    ConversionError,
    UseCaseError,
)


def _diagram() -> dict[str, object]:
    return {
        "nodes": [
            {"uid": "actor", "name": "Customer", "type": "actor"},
            {"uid": "usecase", "name": "Order", "type": "usecase"},
        ],
        "relations": [
            {
                "uid": "relation",
                "source": "actor",
                "target": "usecase",
                "type": "association",
            }
        ],
    }


def _layout(name: str = "Customer") -> ApollonLayout:
    bounds = ApollonLayoutBounds(x=10, y=20, width=80, height=40)
    return ApollonLayout(
        size=ApollonLayoutSize(width=200, height=120),
        elements={
            "actor": ApollonLayoutNode(
                id="actor",
                name=name,
                type=ApollonNodeType.ACTOR,
                bounds=bounds,
            )
        },
        relationships={
            "relation": ApollonLayoutRelation(
                id="relation",
                type=ApollonRelationType.ASSOCIATION,
                bounds=bounds,
                path=[ApollonLayoutPoint(x=0, y=0)],
                source=ApollonLayoutEndpoint(
                    direction=ApollonLayoutDirection.RIGHT, element="actor"
                ),
                target=ApollonLayoutEndpoint(
                    direction=ApollonLayoutDirection.LEFT, element="usecase"
                ),
            )
        },
    )


class FakeConverter:
    def __init__(self) -> None:
        self.calls: list[ApollonLayoutConverterInput] = []

    async def execute(
        self, data: ApollonLayoutConverterInput
    ) -> ApollonLayout:
        self.calls.append(data)
        return _layout(data.diagram.nodes[0].name)


class FailingConverter(FakeConverter):
    def __init__(self, error: BaseAppException) -> None:
        super().__init__()
        self.error = error

    async def execute(
        self, data: ApollonLayoutConverterInput
    ) -> ApollonLayout:
        self.calls.append(data)
        raise self.error


class ConverterProvider(Provider):
    def __init__(self, converter: FakeConverter) -> None:
        super().__init__()
        self.converter = converter

    @provide(scope=Scope.APP)
    def apollon_layout_converter(self) -> ApollonLayoutConverter:
        return cast(ApollonLayoutConverter, self.converter)


@pytest.mark.anyio
async def test_authenticated_client_converts_diagram_to_apollon_layout() -> (
    None
):
    converter = FakeConverter()
    container = make_api_container(
        ConverterProvider(converter),
        settings=ApiSettings(API_SECRET="secret"),
    )
    app = create_app(container=container)

    async with app.router.lifespan_context(app):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/api/v1/converters/apollon",
                headers={"X-API-Key": "secret"},
                json=_diagram(),
            )

    assert response.status_code == 200
    assert response.json() == {
        "ok": True,
        "data": {
            "version": "3.0.0",
            "type": "UseCaseDiagram",
            "size": {"width": 200.0, "height": 120.0},
            "interactive": {"elements": {}, "relationships": {}},
            "elements": {
                "actor": {
                    "id": "actor",
                    "name": "Customer",
                    "type": "UseCaseActor",
                    "owner": None,
                    "bounds": {
                        "x": 10.0,
                        "y": 20.0,
                        "width": 80.0,
                        "height": 40.0,
                    },
                }
            },
            "relationships": {
                "relation": {
                    "id": "relation",
                    "name": "",
                    "type": "UseCaseAssociation",
                    "owner": None,
                    "bounds": {
                        "x": 10.0,
                        "y": 20.0,
                        "width": 80.0,
                        "height": 40.0,
                    },
                    "path": [{"x": 0.0, "y": 0.0}],
                    "source": {"direction": "Right", "element": "actor"},
                    "target": {"direction": "Left", "element": "usecase"},
                    "isManuallyLayouted": False,
                }
            },
            "assessments": {},
        },
    }


@pytest.mark.anyio
async def test_converter_route_requires_documented_api_key_and_has_no_alias() -> (
    None
):
    converter = FakeConverter()
    container = make_api_container(
        ConverterProvider(converter),
        settings=ApiSettings(API_SECRET="secret"),
    )
    app = create_app(container=container)

    async with app.router.lifespan_context(app):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            unauthorized = await client.post(
                "/api/v1/converters/apollon", json=_diagram()
            )
            former = await client.post(
                "/v1/converters/apollon",
                headers={"X-API-Key": "secret"},
                json=_diagram(),
            )
            schema = (await client.get("/openapi.json")).json()

    assert unauthorized.status_code == 401
    assert former.status_code == 404
    assert schema["paths"]["/api/v1/converters/apollon"]["post"][
        "security"
    ] == [{"APIKeyHeader": []}]
    assert converter.calls == []


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("error", "status_code", "error_code"),
    [
        (
            ConversionError("secret input", original=ValueError()),
            422,
            "CONVERSION_ERROR",
        ),
        (
            UseCaseError("secret failure", original=ValueError()),
            500,
            "USE_CASE_ERROR",
        ),
    ],
)
async def test_converter_failures_use_stable_service_error_contract(
    error: BaseAppException, status_code: int, error_code: str
) -> None:
    converter = FailingConverter(error)
    container = make_api_container(
        ConverterProvider(converter),
        settings=ApiSettings(API_SECRET="secret"),
    )
    app = create_app(container=container)

    async with app.router.lifespan_context(app):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/api/v1/converters/apollon",
                headers={"X-API-Key": "secret"},
                json=_diagram(),
            )

    assert response.status_code == status_code
    assert response.json() == {
        "ok": False,
        "error_code": error_code,
        "error_message": "The operation could not be completed.",
    }
    assert "secret" not in response.text
