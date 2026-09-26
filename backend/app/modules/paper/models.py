from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Column,
    DateTime,
    Enum as SAEnum,
    Numeric,
    Text,
    UniqueConstraint,
)
from sqlmodel import Field, SQLModel

from app.core.clock import utc_now
from .types import PaperStatus


class Paper(SQLModel, table=True):
    __tablename__ = "paper"
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    creator_id: UUID = Field(foreign_key="user_account.id")
    title: str = Field(max_length=200)
    description: str | None = Field(default=None, sa_column=Column(Text))
    status: PaperStatus = Field(
        default=PaperStatus.ACTIVE,
        sa_column=Column(SAEnum(PaperStatus, name="paper_status"), nullable=False),
    )
    version: int = Field(default=1, sa_type=BigInteger)
    created_at: datetime = Field(default_factory=utc_now, sa_type=DateTime(timezone=True))
    updated_at: datetime = Field(default_factory=utc_now, sa_type=DateTime(timezone=True))


class PaperQuestion(SQLModel, table=True):
    __tablename__ = "paper_question"
    __table_args__ = (
        UniqueConstraint("paper_id", "question_id"),
        UniqueConstraint("paper_id", "order_no", deferrable=True, initially="DEFERRED"),
        CheckConstraint("order_no > 0"),
        CheckConstraint("score > 0"),
    )
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    paper_id: UUID = Field(foreign_key="paper.id")
    question_id: UUID = Field(foreign_key="question.id")
    order_no: int
    score: Decimal = Field(sa_column=Column(Numeric(10, 1), nullable=False))
