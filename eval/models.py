from pydantic import BaseModel


class ClassificationCounts(BaseModel):
    true_positive: int
    false_positive: int
    false_negative: int
