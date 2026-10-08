from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, StrictBool
from app.modules.attempt.types import AttemptStatus, GradingStatus
from app.modules.exam.types import ExamStatus, ParticipantStatus
from app.modules.question.schemas import QuestionOption
from app.modules.question.types import Difficulty, QuestionType


class StudentResultSummary(BaseModel):
    exam_id: UUID
    title: str
    exam_status: ExamStatus
    result_state: Literal[
        "NOT_PUBLISHED", "CORRECTING", "PUBLISHED", "CANCELLED", "PARTICIPANT_CANCELLED"
    ]
    participant_status: ParticipantStatus
    end_at: datetime | None
    total_score: Decimal
    allow_review: bool
    can_review: bool
    attempts_count: int
    final_attempt_id: UUID | None
    final_attempt_no: int | None
    grading_status: GradingStatus | None
    final_score: Decimal | None
    submitted_at: datetime | None


class StudentAttemptResult(BaseModel):
    id: UUID
    attempt_no: int
    status: AttemptStatus
    started_at: datetime
    submitted_at: datetime | None
    grading_status: GradingStatus
    final_score: Decimal | None
    can_review: bool


class StudentResultDetail(StudentResultSummary):
    attempts: list[StudentAttemptResult]


class ReviewAnswer(BaseModel):
    id: UUID
    answer_data: list[str] | StrictBool | str | None
    grading_status: GradingStatus
    score: Decimal | None
    is_correct: bool | None
    grader_comment: str | None


class ReviewQuestion(BaseModel):
    id: UUID
    order_no: int
    display_order: int
    type: QuestionType
    content: str
    options: list[QuestionOption]
    standard_answer: list[str] | StrictBool | str | None
    explanation: str | None
    subject: str
    knowledge_tags: list[str]
    difficulty: Difficulty
    score: Decimal
    answer: ReviewAnswer


class StudentReview(BaseModel):
    id: UUID
    exam_id: UUID
    exam_title: str
    attempt_no: int
    submitted_at: datetime | None
    total_score: Decimal
    final_score: Decimal | None
    questions: list[ReviewQuestion]
