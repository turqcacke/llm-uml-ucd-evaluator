from dishka import Provider, Scope, provide

from src.services.diagram_assessment import (
    ApollonToApollonAssessment,
    DescriptionReferenceAssessment,
    GetAssessmentByCandidateId,
    GetAssessmentByUid,
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
    get_assessment_by_candidate_id = provide(
        GetAssessmentByCandidateId,
        scope=Scope.REQUEST,
    )
    get_assessment_by_uid = provide(
        GetAssessmentByUid,
        scope=Scope.REQUEST,
    )
