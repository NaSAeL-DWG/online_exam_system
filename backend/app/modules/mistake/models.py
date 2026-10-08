from datetime import datetime
from uuid import UUID

from sqlalchemy import Column, DateTime, Text
from sqlmodel import Field, SQLModel
from app.core.clock import utc_now


class MistakeAnnotation(SQLModel, table=True):
    """错题学习标记保留历史，是否仍为可见错题由实时查询决定。"""

    __tablename__ = "mistake_annotation"
    user_id: UUID = Field(foreign_key="user_account.id", primary_key=True)
    answer_id: UUID = Field(foreign_key="stu_answer.id", primary_key=True)
    mastered: bool = False
    note: str | None = Field(default=None, sa_column=Column(Text))
    created_at: datetime = Field(default_factory=utc_now, sa_type=DateTime(timezone=True))
    updated_at: datetime = Field(default_factory=utc_now, sa_type=DateTime(timezone=True))
