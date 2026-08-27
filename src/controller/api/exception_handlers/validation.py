from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from src.controller.api.responses import failure


async def validation_error(
    _: Request, exc: Exception
) -> JSONResponse:
    assert isinstance(exc, RequestValidationError)
    reasons = [
        f"{'.'.join(map(str, error['loc'][1:]))}: {error['msg']}"
        for error in exc.errors()
    ]
    return failure(422, "VALIDATION_ERROR", "; ".join(reasons))
