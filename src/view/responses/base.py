from typing import Literal

from pydantic import BaseModel


class SuccessResponse[T](BaseModel):
    ok: Literal[True] = True
    data: T


class FailResponse(BaseModel):
    ok: Literal[False] = False
    error_code: str
    error_message: str
