from datetime import datetime
from decimal import Decimal
from uuid import UUID
from pydantic import BaseModel, Field
from app.modules.question.types import QuestionType
from app.modules.results.schemas import ReviewQuestion


class AnnotationInput(BaseModel):
    note: str | None = Field(default=None, max_length=20000)
    mastered: bool


class AnnotationPublic(BaseModel):
    note: str | None
    mastered: bool


class MistakeSummary(AnnotationPublic):
    answer_id: UUID
    attempt_id: UUID
    attempt_no: int
    exam_id: UUID
    exam_title: str
    submitted_at: datetime | None
    question_id: UUID
    type: QuestionType
    subject: str
    knowledge_tags: list[str]
    content: str
    score: Decimal
    full_score: Decimal


class MistakeDetail(MistakeSummary):
    question: ReviewQuestion
