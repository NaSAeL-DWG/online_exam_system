from enum import StrEnum


class AttemptStatus(StrEnum):
    IN_PROGRESS = "IN_PROGRESS"
    SUBMITTED = "SUBMITTED"
    VOID = "VOID"


class SubmissionType(StrEnum):
    MANUAL = "MANUAL"
    TIMEOUT = "TIMEOUT"


class GradingStatus(StrEnum):
    PENDING = "PENDING"
    GRADING = "GRADING"
    GRADED = "GRADED"


class GradingMethod(StrEnum):
    AUTO = "AUTO"
    MANUAL = "MANUAL"
