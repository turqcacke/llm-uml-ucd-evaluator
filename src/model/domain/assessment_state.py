from enum import StrEnum


class AssessmentState(StrEnum):
    EXTRACTING = "extracting"
    ANALYZING = "analyzing"
    SAVING = "saving"
    COMPLETED = "completed"
