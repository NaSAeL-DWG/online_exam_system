from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator
from app.modules.paper.schemas import Score

from app.modules.question.schemas import QuestionContent
from .types import AudienceType, ExamStatus, MultipleChoiceMode


class ExamCreate(BaseModel):
    source_paper_id: UUID
    title: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=100000)
    audience_type: AudienceType


class ExamQuestionPublic(QuestionContent):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    source_question_id: UUID | None
    order_no: int
    score: Decimal


class ExamSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    creator_id: UUID
    source_paper_id: UUID
    title: str
    description: str | None
    audience_type: AudienceType
    status: ExamStatus
    start_at: datetime | None
    end_at: datetime | None
    duration_seconds: int | None
    max_attempts: int
    allow_review: bool
    shuffle_questions: bool
    shuffle_options: bool
    multiple_choice_mode: MultipleChoiceMode
    pass_percentage: Decimal
    total_score: Decimal
    content_revision: int
    grading_revision: int
    version: int
    released_at: datetime | None
    warnings: list[str]
    created_at: datetime
    updated_at: datetime


class ExamDetail(ExamSummary):
    questions: list[ExamQuestionPublic]
    grader_ids: list[UUID]


class SnapshotEdit(QuestionContent):
    id: UUID | None = None
    source_question_id: UUID | None = None
    score: Score


class SourceQuestionInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source_question_id: UUID
    score: Score


class ExamUpdate(BaseModel):
    version: int = Field(ge=1)
    title: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=100000)
    audience_type: AudienceType
    start_at: AwareDatetime | None = None
    end_at: AwareDatetime | None = None
    duration_seconds: int | None = Field(default=None, gt=0, le=604800)
    max_attempts: int = Field(default=1, gt=0, le=100)
    allow_review: bool = False
    shuffle_questions: bool = False
    shuffle_options: bool = False
    multiple_choice_mode: MultipleChoiceMode = MultipleChoiceMode.EXACT
    pass_percentage: Decimal = Field(
        default=Decimal("60.00"), ge=0, le=100, decimal_places=2, allow_inf_nan=False
    )
    grader_ids: list[UUID] = Field(default_factory=list, max_length=100)
    questions: list[SnapshotEdit | SourceQuestionInput] = Field(max_length=500)

    @model_validator(mode="after")
    def validate_draft(self):
        if not self.title.strip():
            raise ValueError("考试标题不能为空")
        if self.start_at and self.end_at and self.start_at >= self.end_at:
            raise ValueError("开始时间须早于结束时间")
        ids = [
            row.id for row in self.questions if isinstance(row, SnapshotEdit) and row.id is not None
        ]
        sources = [
            row.source_question_id for row in self.questions if row.source_question_id is not None
        ]
        if len(set(ids)) != len(ids) or len(set(sources)) != len(sources):
            raise ValueError("考试内不能重复加入同一题目")
        if sum((row.score for row in self.questions), Decimal("0.0")) > Decimal("999999999.9"):
            raise ValueError("考试总分超过允许范围")
        return self
