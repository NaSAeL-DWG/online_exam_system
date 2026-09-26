from datetime import datetime
from decimal import Decimal
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.modules.question.schemas import QuestionPublic
from .types import PaperStatus

Score = Annotated[Decimal, Field(gt=0, max_digits=10, decimal_places=1, allow_inf_nan=False)]


class PaperQuestionInput(BaseModel):
    question_id: UUID
    score: Score


class PaperInput(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=100000)
    questions: list[PaperQuestionInput] = Field(default_factory=list, max_length=500)

    @field_validator("title")
    @classmethod
    def nonblank_title(cls, value):
        if not value.strip():
            raise ValueError("标题不能为空")
        return value

    @model_validator(mode="after")
    def unique_questions(self):
        if len({item.question_id for item in self.questions}) != len(self.questions):
            raise ValueError("同一试卷不能重复选入相同题目")
        if sum((item.score for item in self.questions), Decimal("0.0")) > Decimal("999999999.9"):
            raise ValueError("试卷总分超过允许范围")
        return self


class PaperUpdate(PaperInput):
    version: int = Field(ge=1)


class PaperSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    creator_id: UUID
    title: str
    description: str | None
    status: PaperStatus
    version: int
    created_at: datetime
    updated_at: datetime
    total_score: Decimal
    question_count: int


class PaperQuestionPublic(BaseModel):
    id: UUID
    question_id: UUID
    order_no: int
    score: Decimal
    question: QuestionPublic


class PaperDetail(PaperSummary):
    questions: list[PaperQuestionPublic]
