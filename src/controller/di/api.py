from anyio import CapacityLimiter
from dishka import Provider, Scope, provide

from src.config import ApiSettings, get_api_settings
from src.infrastructure.apollon import DomainToApollonConverter
from src.services.converter import ApollonLayoutConverter


class ApiProvider(Provider):
    def __init__(self, settings: ApiSettings | None = None) -> None:
        super().__init__()
        self.settings_override = settings

    @provide(scope=Scope.APP)
    def settings(self) -> ApiSettings:
        return self.settings_override or get_api_settings()

    @provide(scope=Scope.APP)
    def limiter(self, settings: ApiSettings) -> CapacityLimiter:
        return CapacityLimiter(settings.GRAPHVIZ_CONCURRENCY_LIMIT)

    domain_to_apollon_converter = provide(
        DomainToApollonConverter, scope=Scope.APP
    )

    @provide(scope=Scope.APP)
    def apollon_layout_converter(
        self,
        converter: DomainToApollonConverter,
        limiter: CapacityLimiter,
    ) -> ApollonLayoutConverter:
        return ApollonLayoutConverter(converter, limiter)
