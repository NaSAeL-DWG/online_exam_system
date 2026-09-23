from datetime import datetime
from enum import StrEnum
from uuid import UUID, uuid4
from sqlalchemy import Column, DateTime, Enum as SAEnum, Text
from sqlmodel import Field, SQLModel
from app.core.clock import utc_now


class ClassStatus(StrEnum):
    ACTIVE = "ACTIVE"
    ARCHIVED = "ARCHIVED"


class MemberRole(StrEnum):
    STUDENT = "STUDENT"
    TEACHER = "TEACHER"


class TeachingClass(SQLModel, table=True):
    __tablename__ = "teaching_class"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    name: str = Field(max_length=200)
    description: str | None = Field(default=None, sa_column=Column(Text))
    creator_id: UUID = Field(foreign_key="user_account.id")
    status: ClassStatus = Field(
        default=ClassStatus.ACTIVE,
        sa_column=Column(SAEnum(ClassStatus, name="class_status"), nullable=False),
    )
    created_at: datetime = Field(default_factory=utc_now, sa_type=DateTime(timezone=True))
    updated_at: datetime = Field(default_factory=utc_now, sa_type=DateTime(timezone=True))


class ClassMember(SQLModel, table=True):
    __tablename__ = "class_member"

    class_id: UUID = Field(foreign_key="teaching_class.id", primary_key=True)
    user_id: UUID = Field(foreign_key="user_account.id", primary_key=True)
    role: MemberRole = Field(
        sa_column=Column(SAEnum(MemberRole, name="member_role"), nullable=False)
    )
    joined_at: datetime = Field(default_factory=utc_now, sa_type=DateTime(timezone=True))
