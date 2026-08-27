from dishka.integrations.fastapi import FromDishka, inject
from fastapi import APIRouter, Security, status
from fastapi.security import APIKeyHeader

from src.services.diagram_assessment import (
    DescriptionReferenceAssessment,
    DescriptionReferenceAssessmentInput,
)
from src.view.responses import (
    AssessmentResult,
    DescriptionAssessmentInput,
    SuccessResponse,
)

router = APIRouter(prefix="/v1")
api_key = APIKeyHeader(name="X-API-Key", auto_error=False)


@router.post(
    "/assessments",
    status_code=status.HTTP_201_CREATED,
    response_model=SuccessResponse[AssessmentResult],
    dependencies=[Security(api_key)],
)
@inject
async def create_assessment(
    data: DescriptionAssessmentInput,
    assessment: FromDishka[DescriptionReferenceAssessment],
) -> SuccessResponse[AssessmentResult]:
    result = await assessment.execute(
        DescriptionReferenceAssessmentInput(
            reference_description=data.reference,
            candidate=data.candidate.to_service(),
        )
    )
    return SuccessResponse(data=AssessmentResult.model_validate(result))
