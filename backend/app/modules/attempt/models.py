from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    Enum as SAEnum,
    Index,
    Text,
    UniqueConstraint,
    text,
)
from sqlmodel import Field, SQLModel

from app.core.clock import utc_now
from .types import AttemptStatus


class ExamAttempt(SQLModel, table=True):
    """迭代2必要的真实作答基础；开始/保存/提交完整用例在迭代3补齐。"""

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
    voided_at: datetime | None = Field(default=None, sa_type=DateTime(timezone=True))
    void_reason: str | None = Field(default=None, sa_column=Column(Text))
    version: int = 1
    created_at: datetime = Field(default_factory=utc_now, sa_type=DateTime(timezone=True))
    updated_at: datetime = Field(default_factory=utc_now, sa_type=DateTime(timezone=True))
