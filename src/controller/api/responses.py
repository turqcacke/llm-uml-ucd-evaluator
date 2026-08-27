from fastapi.responses import JSONResponse


def failure(status: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=status,
        content={"ok": False, "error_code": code, "error_message": message},
    )
