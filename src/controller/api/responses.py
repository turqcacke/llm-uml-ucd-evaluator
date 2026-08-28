from collections.abc import Mapping

from fastapi.responses import JSONResponse


def failure(
    status: int,
    code: str,
    message: str,
    headers: Mapping[str, str] | None = None,
) -> JSONResponse:
    return JSONResponse(
        status_code=status,
        content={"ok": False, "error_code": code, "error_message": message},
        headers=headers,
    )
