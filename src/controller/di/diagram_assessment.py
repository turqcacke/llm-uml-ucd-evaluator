from dishka import Provider, Scope, provide

from src.services.diagram_assessment import (
    ApollonToApollonAssessment,
    DescriptionReferenceAssessment,
)


class DiagramAssessmentProvider(Provider):
    description_reference_assessment = provide(
        DescriptionReferenceAssessment,
        scope=Scope.REQUEST,
    )
    apollon_to_apollon_assessment = provide(
        ApollonToApollonAssessment,
        scope=Scope.REQUEST,
    )
