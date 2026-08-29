from collections.abc import AsyncGenerator, AsyncIterator
from contextlib import AsyncExitStack
from typing import Annotated

from anyio import CancelScope
from dishka.integrations.fastapi import FromDishka, inject
from fastapi import APIRouter, Depends, Security, status
from fastapi.sse import EventSourceResponse, ServerSentEvent

from src.controller.api.exception_handlers import (
    INTERNAL_ERROR_MESSAGE,
    SERVICE_ERROR_MESSAGE,
)
from src.controller.api.security import api_key
from src.services.diagram_assessment import (
    ApollonReferenceAssessment,
    ApollonReferenceAssessmentInput,
    DescriptionReferenceAssessment,
    DescriptionReferenceAssessmentInput,
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


async def _stream_cleanup() -> AsyncIterator[AsyncExitStack]:
    cleanup = AsyncExitStack()
    try:
        yield cleanup
    finally:
        with CancelScope(shield=True):
            await cleanup.aclose()


@router.post(
    "/assessments/streams",
    response_class=EventSourceResponse,
    dependencies=[Security(api_key)],
)
@inject
async def stream_assessment(
    data: AssessmentInput,
    cleanup: Annotated[AsyncExitStack, Depends(_stream_cleanup)],
    description_assessment: FromDishka[DescriptionReferenceAssessment],
    apollon_assessment: FromDishka[ApollonReferenceAssessment],
) -> AsyncGenerator[ServerSentEvent]:
    try:
        if isinstance(data, ApollonAssessmentInput):
            progress = apollon_assessment.stream(
                ApollonReferenceAssessmentInput(
                    reference=data.reference.to_service(),
                    candidate=data.candidate.to_service(),
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
