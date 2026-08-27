from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


def failure(status: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=status,
        content={"ok": False, "error_code": code, "error_message": message},
    )


def add_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(RequestValidationError)
    async def validation_error(
        _: Request, exc: RequestValidationError
    ) -> JSONResponse:
        reasons = [
            f"{'.'.join(map(str, error['loc'][1:]))}: {error['msg']}"
            for error in exc.errors()
        ]
        return failure(422, "VALIDATION_ERROR", "; ".join(reasons))
