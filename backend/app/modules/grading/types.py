from enum import StrEnum


class TaskStatus(StrEnum):
    UNASSIGNED = "UNASSIGNED"
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    VOID = "VOID"
