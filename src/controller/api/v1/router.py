from collections.abc import AsyncGenerator, AsyncIterator
from contextlib import AsyncExitStack
from typing import Annotated

from anyio import CancelScope
from dishka.integrations.fastapi import FromDishka, inject
from fastapi import APIRouter, Depends, HTTPException, Security, status
from fastapi.sse import EventSourceResponse, ServerSentEvent

from src.controller.api.descriptions import ASSESSMENT_DESCRIPTION
from src.controller.api.exception_handlers import (
    INTERNAL_ERROR_MESSAGE,
    SERVICE_ERROR_MESSAGE,
)
from src.controller.api.security import api_key
from src.model.apollon import ApollonLayout
from src.model.domain import UseCaseDiagramPresentation
from src.services.converter import (
    ApollonLayoutConverter,
    ApollonLayoutConverterInput,
)
from src.services.diagram_assessment import (
    ApollonToApollonAssessment,
    ApollonToApollonAssessmentInput,
    DescriptionReferenceAssessment,
    DescriptionReferenceAssessmentInput,
    GetAssessmentByCandidateId,
    GetAssessmentByUid,
)
from src.services.exceptions import BaseAppException
from src.view.responses import (
    ApollonAssessmentInput,
    AssessmentInput,
    AssessmentProgress,
    AssessmentResult,
    AssessmentStreamResult,
    FailResponse,
    SuccessResponse,
)

router = APIRouter(prefix="/api/v1")


@router.get(
    "/assessments/candidates/{candidate_id}",
    tags=["Assessments"],
    response_model=SuccessResponse[AssessmentResult],
    dependencies=[Security(api_key)],
)
@inject
async def get_assessment_by_candidate_id(
    candidate_id: str,
    get_assessment: FromDishka[GetAssessmentByCandidateId],
) -> SuccessResponse[AssessmentResult]:
    result = await get_assessment.execute(candidate_id)
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    return SuccessResponse(data=AssessmentResult.model_validate(result))


@router.get(
    "/assessments/{assessment_uid}",
    tags=["Assessments"],
    response_model=SuccessResponse[AssessmentResult],
    dependencies=[Security(api_key)],
)
@inject
async def get_assessment_by_uid(
    assessment_uid: str,
    get_assessment: FromDishka[GetAssessmentByUid],
) -> SuccessResponse[AssessmentResult]:
    result = await get_assessment.execute(assessment_uid)
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    return SuccessResponse(data=AssessmentResult.model_validate(result))


@router.post(
    "/converters/apollon",
    tags=["Converters"],
    response_model=SuccessResponse[ApollonLayout],
    dependencies=[Security(api_key)],
)
@inject
async def convert_to_apollon_layout(
    data: UseCaseDiagramPresentation,
    converter: FromDishka[ApollonLayoutConverter],
) -> SuccessResponse[ApollonLayout]:
    layout = await converter.execute(ApollonLayoutConverterInput(data))
    return SuccessResponse(data=layout)


@router.post(
    "/assessments",
    tags=["Assessments"],
    status_code=status.HTTP_201_CREATED,
    response_model=SuccessResponse[AssessmentResult],
    description=ASSESSMENT_DESCRIPTION,
    dependencies=[Security(api_key)],
)
@inject
async def create_assessment(
    data: AssessmentInput,
    description_assessment: FromDishka[DescriptionReferenceAssessment],
    apollon_assessment: FromDishka[ApollonToApollonAssessment],
) -> SuccessResponse[AssessmentResult]:
    if isinstance(data, ApollonAssessmentInput):
        result = await apollon_assessment.execute(
            ApollonToApollonAssessmentInput(
                reference=data.reference.to_service(),
                candidate=data.candidate.to_service(),
                description=data.description,
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


async def _stream_cleanup() -> AsyncIterator[AsyncExitStack]:
    cleanup = AsyncExitStack()
    try:
        yield cleanup
    finally:
        with CancelScope(shield=True):
            await cleanup.aclose()


@router.post(
    "/assessments/streams",
    tags=["Assessments"],
    response_class=EventSourceResponse,
    description=ASSESSMENT_DESCRIPTION,
    dependencies=[Security(api_key)],
)
@inject
async def stream_assessment(
    data: AssessmentInput,
    cleanup: Annotated[AsyncExitStack, Depends(_stream_cleanup)],
    description_assessment: FromDishka[DescriptionReferenceAssessment],
    apollon_assessment: FromDishka[ApollonToApollonAssessment],
) -> AsyncGenerator[ServerSentEvent]:
    try:
        if isinstance(data, ApollonAssessmentInput):
            progress = apollon_assessment.stream(
                ApollonToApollonAssessmentInput(
                    reference=data.reference.to_service(),
                    candidate=data.candidate.to_service(),
                    description=data.description,
                )
            )
        else:
            progress = description_assessment.stream(
                DescriptionReferenceAssessmentInput(
                    reference_description=data.reference,
                    candidate=data.candidate.to_service(),
                )
            )

        # The SSE producer may stop while this iterator is suspended at yield.
        cleanup.push_async_callback(progress.aclose)
        async for state, result in progress:
            if result is None:
                yield ServerSentEvent(
                    event="progress",
                    data=AssessmentProgress(state=state),
                )
            else:
                yield ServerSentEvent(
                    event="result",
                    data=AssessmentStreamResult(
                        state=state,
                        data=AssessmentResult.model_validate(result),
                    ),
                )
                return
    except BaseAppException as exc:
        yield ServerSentEvent(
            event="error",
            data=FailResponse(
                error_code=exc.error_code,
                error_message=SERVICE_ERROR_MESSAGE,
            ),
        )
    except Exception:
        yield ServerSentEvent(
            event="error",
            data=FailResponse(
                error_code="INTERNAL_ERROR",
                error_message=INTERNAL_ERROR_MESSAGE,
            ),
        )
