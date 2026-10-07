from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import BigInteger, Column, DateTime, Enum as SAEnum, Index, Numeric, Text
from sqlmodel import Field, SQLModel

from app.core.clock import utc_now
from app.modules.attempt.types import GradingMethod
from .types import TaskStatus


class GradingTask(SQLModel, table=True):
    """整份答卷的人工阅卷工作，首次完成事实不随重判撤销。"""

    __tablename__ = "grading_task"
    __table_args__ = (Index("ix_task_teacher_status", "assigned_teacher_id", "status"),)
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    attempt_id: UUID = Field(foreign_key="exam_attempt.id", unique=True)
    assigned_teacher_id: UUID | None = Field(default=None, foreign_key="user_account.id")
    status: TaskStatus = Field(
        default=TaskStatus.UNASSIGNED,
        sa_column=Column(SAEnum(TaskStatus, name="grading_task_status"), nullable=False),
    )
    grading_revision: int = Field(default=1, sa_type=BigInteger)
    first_review_completed_at: datetime | None = Field(
        default=None, sa_type=DateTime(timezone=True)
    )
    completed_at: datetime | None = Field(default=None, sa_type=DateTime(timezone=True))
    assigned_at: datetime | None = Field(default=None, sa_type=DateTime(timezone=True))
    version: int = Field(default=1, sa_type=BigInteger)
    created_at: datetime = Field(default_factory=utc_now, sa_type=DateTime(timezone=True))
    updated_at: datetime = Field(default_factory=utc_now, sa_type=DateTime(timezone=True))


class GradingHistory(SQLModel, table=True):
    __tablename__ = "grading_history"
    __table_args__ = (Index("ix_grading_history_answer_created", "answer_id", "created_at"),)
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    answer_id: UUID = Field(foreign_key="stu_answer.id")
    grading_revision: int = Field(sa_type=BigInteger)
    answer_version: int = Field(default=1, sa_type=BigInteger)
    actor_id: UUID | None = Field(default=None, foreign_key="user_account.id")
    method: GradingMethod = Field(
        sa_column=Column(SAEnum(GradingMethod, name="grading_method"), nullable=False)
    )
    old_score: Decimal | None = Field(default=None, sa_type=Numeric(10, 1))
    new_score: Decimal = Field(sa_type=Numeric(10, 1))
    old_is_correct: bool | None = None
    new_is_correct: bool
    old_comment: str | None = Field(default=None, sa_column=Column(Text))
    new_comment: str | None = Field(default=None, sa_column=Column(Text))
    reason: str | None = Field(default=None, sa_column=Column(Text))
    created_at: datetime = Field(default_factory=utc_now, sa_type=DateTime(timezone=True))
