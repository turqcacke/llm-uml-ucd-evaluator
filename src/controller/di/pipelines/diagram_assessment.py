from dishka import Provider, Scope, provide

from src.services.pipelines.diagram_assessment import (
    ApollonReferenceAssessment,
    DescriptionReferenceAssessment,
)


class DiagramAssessmentProvider(Provider):
    description_reference_assessment = provide(
        DescriptionReferenceAssessment,
        scope=Scope.APP,
    )
    apollon_reference_assessment = provide(
        ApollonReferenceAssessment,
        scope=Scope.APP,
    )
