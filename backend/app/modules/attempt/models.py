from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    BigInteger,
    Column,
    DateTime,
    Enum as SAEnum,
    Index,
    Numeric,
    Text,
    UniqueConstraint,
    text,
)
from sqlmodel import Field, SQLModel
from sqlalchemy.dialects.postgresql import JSONB

from app.core.clock import utc_now
from .types import AttemptStatus, GradingMethod, GradingStatus, SubmissionType


class ExamAttempt(SQLModel, table=True):
    """独立计时作答；数据库状态是保存、接管和可靠提交的依据。"""

    __tablename__ = "exam_attempt"
    __table_args__ = (
        UniqueConstraint("exam_participant_id", "attempt_no"),
        CheckConstraint("attempt_no > 0"),
        Index(
            "uq_attempt_in_progress",
            "exam_participant_id",
            unique=True,
            postgresql_where=text("status = 'IN_PROGRESS'::attempt_status"),
        ),
        Index(
            "ix_attempt_deadline",
            "deadline_at",
            postgresql_where=text("status = 'IN_PROGRESS'::attempt_status"),
        ),
    )
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    exam_participant_id: UUID = Field(foreign_key="exam_participant.id")
    attempt_no: int
    status: AttemptStatus = Field(
        default=AttemptStatus.IN_PROGRESS,
        sa_column=Column(SAEnum(AttemptStatus, name="attempt_status"), nullable=False),
    )
    started_at: datetime = Field(sa_type=DateTime(timezone=True))
    deadline_at: datetime = Field(sa_type=DateTime(timezone=True))
    last_active_at: datetime | None = Field(default=None, sa_type=DateTime(timezone=True))
    submitted_at: datetime | None = Field(default=None, sa_type=DateTime(timezone=True))
    effective_submitted_at: datetime | None = Field(default=None, sa_type=DateTime(timezone=True))
    submission_type: SubmissionType | None = Field(
        default=None, sa_column=Column(SAEnum(SubmissionType, name="submission_type"))
    )
    grading_status: GradingStatus = Field(
        default=GradingStatus.PENDING,
        sa_column=Column(SAEnum(GradingStatus, name="grading_status"), nullable=False),
    )
    grading_revision: int = Field(default=1, sa_type=BigInteger)
    final_score: Decimal | None = Field(default=None, sa_type=Numeric(10, 1))
    graded_at: datetime | None = Field(default=None, sa_type=DateTime(timezone=True))
    active_token_hash: str | None = Field(default=None, max_length=64)
    active_token_generation: int = Field(default=0, sa_type=BigInteger)
    voided_at: datetime | None = Field(default=None, sa_type=DateTime(timezone=True))
    void_reason: str | None = Field(default=None, sa_column=Column(Text))
    version: int = 1
    created_at: datetime = Field(default_factory=utc_now, sa_type=DateTime(timezone=True))
    updated_at: datetime = Field(default_factory=utc_now, sa_type=DateTime(timezone=True))


class StudentAnswer(SQLModel, table=True):
    __tablename__ = "stu_answer"
    __table_args__ = (
        UniqueConstraint("attempt_id", "exam_question_id"),
        CheckConstraint("score >= 0"),
        Index("ix_answer_attempt_grading", "attempt_id", "grading_status"),
    )
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    attempt_id: UUID = Field(foreign_key="exam_attempt.id")
    exam_question_id: UUID = Field(foreign_key="exam_question.id")
    answer_data: list[str] | bool | str | None = Field(default=None, sa_column=Column(JSONB))
    grading_status: GradingStatus = Field(
        default=GradingStatus.PENDING,
        sa_column=Column(SAEnum(GradingStatus, name="grading_status"), nullable=False),
    )
    grading_revision: int = Field(default=1, sa_type=BigInteger)
    score: Decimal | None = Field(default=None, sa_type=Numeric(10, 1))
    is_correct: bool | None = None
    grader_comment: str | None = Field(default=None, sa_column=Column(Text))
    graded_by: UUID | None = Field(default=None, foreign_key="user_account.id")
    grading_method: GradingMethod | None = Field(
        default=None, sa_column=Column(SAEnum(GradingMethod, name="grading_method"))
    )
    graded_at: datetime | None = Field(default=None, sa_type=DateTime(timezone=True))
    version: int = Field(default=1, sa_type=BigInteger)
    answered_at: datetime | None = Field(default=None, sa_type=DateTime(timezone=True))
    created_at: datetime = Field(default_factory=utc_now, sa_type=DateTime(timezone=True))
    updated_at: datetime = Field(default_factory=utc_now, sa_type=DateTime(timezone=True))


class AttemptQuestionOrder(SQLModel, table=True):
    __tablename__ = "attempt_question_order"
    __table_args__ = (
        UniqueConstraint("attempt_id", "display_order"),
        CheckConstraint("display_order > 0"),
    )
    attempt_id: UUID = Field(foreign_key="exam_attempt.id", primary_key=True)
    exam_question_id: UUID = Field(foreign_key="exam_question.id", primary_key=True)
    display_order: int
    option_order: list[str] = Field(default_factory=list, sa_column=Column(JSONB, nullable=False))
