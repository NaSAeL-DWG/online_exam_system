from datetime import datetime
from decimal import Decimal
from uuid import UUID
from pydantic import BaseModel
from app.modules.exam.types import AudienceType, ExamStatus
from app.modules.question.types import QuestionType


class ScoreBand(BaseModel):
    label: str
    lower_rate: Decimal
    upper_rate: Decimal
    count: int


class QuestionRate(BaseModel):
    question_id: UUID
    order_no: int
    type: QuestionType
    subject: str
    content: str
    full_score: Decimal
    sample_count: int
    score_sum: Decimal
    score_rate: Decimal | None


class TeacherAnalytics(BaseModel):
    exam_id: UUID
    title: str
    exam_status: ExamStatus
    audience_type: AudienceType
    total_score: Decimal
    pass_percentage: Decimal
    ended: bool
    expected_count: int | None
    participated_count: int
    submitted_count: int
    absent_count: int | None
    participation_rate: Decimal | None
    in_progress_count: int
    pending_grading_count: int
    graded_count: int
    attempts_count: int
    submitted_attempts_count: int
    grading_tasks_count: int
    pending_grading_tasks_count: int
    average_score: Decimal | None
    highest_score: Decimal | None
    lowest_score: Decimal | None
    pass_rate: Decimal | None
    score_distribution: list[ScoreBand]
    question_rates: list[QuestionRate]
    notes: list[str]


class ResultTrend(BaseModel):
    exam_id: UUID
    title: str
    end_at: datetime | None
    submitted_at: datetime | None
    final_score: Decimal
    total_score: Decimal
    score_rate: Decimal


class TypePerformance(BaseModel):
    type: QuestionType
    answer_count: int
    score_sum: Decimal
    full_score_sum: Decimal
    score_rate: Decimal


class KnowledgeMistake(BaseModel):
    knowledge_tag: str
    count: int


class StudentAnalytics(BaseModel):
    sample_exam_count: int
    review_exam_count: int
    trend: list[ResultTrend]
    type_performance: list[TypePerformance]
    knowledge_mistakes: list[KnowledgeMistake]
    knowledge_note: str
