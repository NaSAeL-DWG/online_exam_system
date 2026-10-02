from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictStr

from app.modules.question.types import QuestionType
from .types import AttemptStatus, GradingStatus, SubmissionType


class AnswerPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    answer_data: list[StrictStr] | StrictBool | StrictStr | None
    version: int
    answered_at: datetime | None


class AttemptOption(BaseModel):
    id: UUID
    content: str


class AttemptQuestion(BaseModel):
    id: UUID
    type: QuestionType
    content: str
    options: list[AttemptOption]
    score: Decimal
    display_order: int
    answer: AnswerPublic


class AttemptDetail(BaseModel):
    id: UUID
    exam_id: UUID
    exam_title: str
    attempt_no: int
    status: AttemptStatus
    started_at: datetime
    deadline_at: datetime
    submitted_at: datetime | None
    effective_submitted_at: datetime | None
    submission_type: SubmissionType | None
    grading_status: GradingStatus
    server_now: datetime
    version: int
    token_generation: int
    questions: list[AttemptQuestion]


class ActivateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    page_token: StrictStr | None = Field(default=None, min_length=32, max_length=256)


class AttemptActivation(AttemptDetail):
    page_token: str


class PageWriteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    page_token: StrictStr = Field(min_length=32, max_length=256)
    token_generation: int = Field(ge=1)


class AnswerSave(PageWriteRequest):
    version: int = Field(ge=1)
    answer_data: list[StrictStr] | StrictBool | StrictStr | None


class SubmitRequest(PageWriteRequest):
    confirm_unanswered: StrictBool = False
