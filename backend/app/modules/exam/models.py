from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Column,
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    Index,
    Numeric,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlmodel import Field, SQLModel

from app.core.clock import utc_now
from app.modules.question.types import Difficulty, QuestionType
from .types import AudienceType, ExamStatus, MultipleChoiceMode, ParticipantStatus


class Exam(SQLModel, table=True):
    __tablename__ = "exam"
    __table_args__ = (
        Index("ix_exam_status_end", "status", "end_at"),
        CheckConstraint("total_score >= 0"),
        CheckConstraint("pass_percentage BETWEEN 0 AND 100"),
    )
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    creator_id: UUID = Field(foreign_key="user_account.id")
    source_paper_id: UUID = Field(foreign_key="paper.id")
    title: str = Field(max_length=200)
    description: str | None = Field(default=None, sa_column=Column(Text))
    audience_type: AudienceType = Field(
        sa_column=Column(SAEnum(AudienceType, name="audience_type"), nullable=False)
    )
    status: ExamStatus = Field(
        default=ExamStatus.DRAFT,
        sa_column=Column(SAEnum(ExamStatus, name="exam_status"), nullable=False),
    )
    start_at: datetime | None = Field(default=None, sa_type=DateTime(timezone=True))
    end_at: datetime | None = Field(default=None, sa_type=DateTime(timezone=True))
    duration_seconds: int | None = None
    max_attempts: int = 1
    allow_review: bool = False
    shuffle_questions: bool = False
    shuffle_options: bool = False
    multiple_choice_mode: MultipleChoiceMode = Field(
        default=MultipleChoiceMode.EXACT,
        sa_column=Column(SAEnum(MultipleChoiceMode, name="multiple_choice_mode"), nullable=False),
    )
    pass_percentage: Decimal = Field(
        default=Decimal("60.00"), sa_column=Column(Numeric(5, 2), nullable=False)
    )
    total_score: Decimal = Field(
        default=Decimal("0.0"), sa_column=Column(Numeric(10, 1), nullable=False)
    )
    content_revision: int = Field(default=1, sa_type=BigInteger)
    grading_revision: int = Field(default=1, sa_type=BigInteger)
    version: int = Field(default=1, sa_type=BigInteger)
    warnings: list[str] = Field(default_factory=list, sa_column=Column(JSONB, nullable=False))
    released_at: datetime | None = Field(default=None, sa_type=DateTime(timezone=True))
    created_at: datetime = Field(default_factory=utc_now, sa_type=DateTime(timezone=True))
    updated_at: datetime = Field(default_factory=utc_now, sa_type=DateTime(timezone=True))


class ExamQuestion(SQLModel, table=True):
    __tablename__ = "exam_question"
    __table_args__ = (
        UniqueConstraint("exam_id", "source_question_id"),
        UniqueConstraint("exam_id", "order_no", deferrable=True, initially="DEFERRED"),
        CheckConstraint("order_no > 0"),
        CheckConstraint("score > 0"),
    )
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    exam_id: UUID = Field(foreign_key="exam.id")
    source_question_id: UUID | None = Field(default=None, foreign_key="question.id")
    source_paper_question_id: UUID | None = Field(
        default=None,
        sa_column=Column(
            PGUUID(as_uuid=True), ForeignKey("paper_question.id", ondelete="SET NULL")
        ),
    )
    order_no: int
    score: Decimal = Field(sa_column=Column(Numeric(10, 1), nullable=False))
    type: QuestionType = Field(
        sa_column=Column(SAEnum(QuestionType, name="question_type"), nullable=False)
    )
    content: str = Field(sa_column=Column(Text, nullable=False))
    options: list[dict] = Field(default_factory=list, sa_column=Column(JSONB, nullable=False))
    standard_answer: list[str] | bool | str | None = Field(default=None, sa_column=Column(JSONB))
    explanation: str | None = Field(default=None, sa_column=Column(Text))
    subject: str = Field(max_length=100)
    knowledge_tags: list[str] = Field(default_factory=list, sa_column=Column(JSONB, nullable=False))
    difficulty: Difficulty = Field(
        sa_column=Column(SAEnum(Difficulty, name="question_difficulty"), nullable=False)
    )
    grading_revision: int = Field(default=1, sa_type=BigInteger)
    created_at: datetime = Field(default_factory=utc_now, sa_type=DateTime(timezone=True))
    updated_at: datetime = Field(default_factory=utc_now, sa_type=DateTime(timezone=True))


class ExamGrader(SQLModel, table=True):
    __tablename__ = "exam_grader"
    exam_id: UUID = Field(foreign_key="exam.id", primary_key=True)
    teacher_id: UUID = Field(foreign_key="user_account.id", primary_key=True)
    assigned_by: UUID = Field(foreign_key="user_account.id")
    assigned_at: datetime = Field(default_factory=utc_now, sa_type=DateTime(timezone=True))


class ExamParticipant(SQLModel, table=True):
    __tablename__ = "exam_participant"
    __table_args__ = (
        UniqueConstraint("exam_id", "user_id"),
        Index("ix_participant_user_status_exam", "user_id", "status", "exam_id"),
        Index("ix_participant_exam_status", "exam_id", "status"),
    )
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    exam_id: UUID = Field(foreign_key="exam.id")
    user_id: UUID = Field(foreign_key="user_account.id")
    status: ParticipantStatus = Field(
        default=ParticipantStatus.ASSIGNED,
        sa_column=Column(SAEnum(ParticipantStatus, name="participant_status"), nullable=False),
    )
    assigned_at: datetime = Field(default_factory=utc_now, sa_type=DateTime(timezone=True))
    cancelled_at: datetime | None = Field(default=None, sa_type=DateTime(timezone=True))
    cancelled_reason: str | None = Field(default=None, sa_column=Column(Text))
    version: int = Field(default=1, sa_type=BigInteger)
    created_at: datetime = Field(default_factory=utc_now, sa_type=DateTime(timezone=True))
    updated_at: datetime = Field(default_factory=utc_now, sa_type=DateTime(timezone=True))
