from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, Field
from .models import ClassStatus, MemberRole
from app.modules.identity.schemas import UserSummary


class ClassCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = None
    teacher_ids: list[UUID] = Field(default_factory=list)


class ClassPatchRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None
    status: ClassStatus | None = None
    teacher_ids: list[UUID] | None = None


class MemberPutRequest(BaseModel):
    role: MemberRole


class ClassPublic(BaseModel):
    id: UUID
    name: str
    description: str | None
    status: ClassStatus
    teachers: list[UserSummary]
    students: list[UserSummary] | None = None
    student_count: int
    created_at: datetime
    updated_at: datetime


class ClassResponse(BaseModel):
    class_info: ClassPublic
