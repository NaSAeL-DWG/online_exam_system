from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StrictBool, field_validator

from app.modules.attempt.types import AttemptStatus, GradingMethod, GradingStatus
from app.modules.identity.schemas import UserSummary
from app.modules.question.schemas import QuestionOption
from app.modules.question.types import QuestionType
from .types import TaskStatus


class TaskPublic(BaseModel):
    id: UUID
    attempt_id: UUID
    assigned_teacher: UserSummary | None
    status: TaskStatus
    grading_revision: int
    first_review_completed_at: datetime | None
    completed_at: datetime | None
    assigned_at: datetime | None
    version: int


class AttemptSummary(BaseModel):
    id: UUID
    exam_id: UUID
    exam_title: str
    student: UserSummary
    attempt_no: int
    status: AttemptStatus
    submitted_at: datetime | None
    effective_submitted_at: datetime | None
    grading_status: GradingStatus
    grading_revision: int
    final_score: Decimal | None
    graded_at: datetime | None
    task: TaskPublic | None


class AnswerPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    answer_data: list[str] | StrictBool | str | None
    version: int
    grading_status: GradingStatus
    grading_revision: int
    score: Decimal | None
    is_correct: bool | None
    grader_comment: str | None
    graded_by: UUID | None
    grading_method: GradingMethod | None
    graded_at: datetime | None


class GradingQuestion(BaseModel):
    id: UUID
    type: QuestionType
    content: str
    options: list[QuestionOption]
    standard_answer: list[str] | StrictBool | str | None
    explanation: str | None
    score: Decimal
    grading_revision: int
    answer: AnswerPublic
    can_grade: bool


class AttemptDetail(AttemptSummary):
    questions: list[GradingQuestion]
    can_grade: bool
    can_reassign: bool
    results_published: bool


class TaskSummary(TaskPublic):
    exam_id: UUID
    exam_title: str
    student: UserSummary
    attempt_no: int
    can_grade: bool
    can_reassign: bool


class ManualGrade(BaseModel):
    version: int = Field(ge=1)
    grading_revision: int = Field(ge=1)
    score: Decimal = Field(ge=0, decimal_places=1, allow_inf_nan=False)
    comment: str | None = Field(default=None, max_length=20000)
    reason: str | None = Field(default=None, max_length=2000)


class ReasonRequest(BaseModel):
    version: int = Field(ge=1)
    reason: str = Field(min_length=1, max_length=2000)

    @field_validator("reason")
    @classmethod
    def nonblank_reason(cls, value):
        if not value.strip():
            raise ValueError("请填写原因")
        return value.strip()


class ReassignRequest(ReasonRequest):
    teacher_id: UUID


class StandardCorrection(ReasonRequest):
    grading_revision: int = Field(ge=1)
    standard_answer: list[str] | StrictBool | str | None
    explanation: str | None = Field(default=None, max_length=100000)


class HistoryPublic(BaseModel):
    id: UUID
    answer_id: UUID
    grading_revision: int
    actor: UserSummary | None
    method: GradingMethod
    old_score: Decimal | None
    new_score: Decimal
    old_is_correct: bool | None
    new_is_correct: bool
    old_comment: str | None
    new_comment: str | None
    reason: str | None
    created_at: datetime


class HistoryResponse(BaseModel):
    items: list[HistoryPublic]


class FinalResult(BaseModel):
    participant_id: UUID
    student: UserSummary
    attempt_id: UUID | None
    attempt_no: int | None
    grading_status: GradingStatus | None
    final_score: Decimal | None
    submitted_at: datetime | None


class RefreshResult(BaseModel):
    graded_attempts: int
    assigned_tasks: int
