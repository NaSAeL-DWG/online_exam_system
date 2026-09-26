from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import BigInteger, Column, DateTime, Enum as SAEnum, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel

from app.core.clock import utc_now
from .types import Difficulty, QuestionStatus, QuestionType


class Question(SQLModel, table=True):
    __tablename__ = "question"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    creator_id: UUID = Field(foreign_key="user_account.id")
    type: QuestionType = Field(
        sa_column=Column(SAEnum(QuestionType, name="question_type"), nullable=False)
    )
    content: str = Field(sa_column=Column(Text, nullable=False))
    options: list[dict] = Field(default_factory=list, sa_column=Column(JSONB, nullable=False))
    standard_answer: list[str] | bool | str | None = Field(default=None, sa_column=Column(JSONB))
    explanation: str | None = Field(default=None, sa_column=Column(Text))
    subject: str = Field(max_length=100, index=True)
    knowledge_tags: list[str] = Field(default_factory=list, sa_column=Column(JSONB, nullable=False))
    difficulty: Difficulty = Field(
        default=Difficulty.MEDIUM,
        sa_column=Column(SAEnum(Difficulty, name="question_difficulty"), nullable=False),
    )
    status: QuestionStatus = Field(
        default=QuestionStatus.ACTIVE,
        sa_column=Column(SAEnum(QuestionStatus, name="question_status"), nullable=False),
    )
    version: int = Field(default=1, sa_type=BigInteger)
    created_at: datetime = Field(default_factory=utc_now, sa_type=DateTime(timezone=True))
    updated_at: datetime = Field(default_factory=utc_now, sa_type=DateTime(timezone=True))
