from pydantic import BaseModel


class Bounds(BaseModel):
    x: float
    y: float
