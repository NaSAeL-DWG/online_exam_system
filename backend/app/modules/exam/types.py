from enum import StrEnum


class ExamStatus(StrEnum):
    DRAFT = "DRAFT"
    RELEASED = "RELEASED"
    RESULTS_PUBLISHED = "RESULTS_PUBLISHED"
    CANCELLED = "CANCELLED"


class AudienceType(StrEnum):
    PUBLIC = "PUBLIC"
    RESTRICTED = "RESTRICTED"


class MultipleChoiceMode(StrEnum):
    EXACT = "EXACT"
    PARTIAL = "PARTIAL"
