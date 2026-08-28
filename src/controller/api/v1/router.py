from dishka.integrations.fastapi import FromDishka, inject
from fastapi import APIRouter, Security, status

from src.controller.api.security import api_key
from src.services.diagram_assessment import (
    ApollonReferenceAssessment,
    ApollonReferenceAssessmentInput,
    DescriptionReferenceAssessment,
    DescriptionReferenceAssessmentInput,
)
from src.view.responses import (
    ApollonAssessmentInput,
    AssessmentInput,
    AssessmentResult,
    SuccessResponse,
)

router = APIRouter(prefix="/v1")


@router.post(
    "/assessments",
    status_code=status.HTTP_201_CREATED,
    response_model=SuccessResponse[AssessmentResult],
    dependencies=[Security(api_key)],
)
@inject
async def create_assessment(
    data: AssessmentInput,
    description_assessment: FromDishka[DescriptionReferenceAssessment],
    apollon_assessment: FromDishka[ApollonReferenceAssessment],
) -> SuccessResponse[AssessmentResult]:
    if isinstance(data, ApollonAssessmentInput):
        result = await apollon_assessment.execute(
            ApollonReferenceAssessmentInput(
                reference=data.reference.to_service(),
                candidate=data.candidate.to_service(),
            )
        )
    else:
        result = await description_assessment.execute(
            DescriptionReferenceAssessmentInput(
                reference_description=data.reference,
                candidate=data.candidate.to_service(),
            )
        )
    return SuccessResponse(data=AssessmentResult.model_validate(result))
