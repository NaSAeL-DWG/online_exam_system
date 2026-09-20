from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator

from .models import ClassStatus, MemberRole, ReviewStatus, UserStatus, UserType


class UserPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    login_name: str
    real_name: str
    email: str
    phone_number: str
    user_type: UserType
    status: UserStatus
    must_change_password: bool
    created_at: datetime


class UserSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    login_name: str
    real_name: str
    user_type: UserType
    status: UserStatus


class ApplicationPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    status: ReviewStatus
    reason: str | None
    submitted_profile: dict[str, Any]
    submitted_at: datetime
    reviewed_at: datetime | None
    reviewer_id: UUID | None


class RegisterRequest(BaseModel):
    student_no: str = Field(min_length=1, max_length=100)
    real_name: str = Field(min_length=1, max_length=100)
    email: EmailStr
    phone_number: str = Field(min_length=5, max_length=32)
    password: str = Field(min_length=10, max_length=256)


class LoginRequest(BaseModel):
    login_name: str
    password: str


class PasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(min_length=10, max_length=256)


class ContactsRequest(BaseModel):
    current_password: str
    email: EmailStr
    phone_number: str = Field(min_length=5, max_length=32)


class ApplicationUpdateRequest(BaseModel):
    student_no: str = Field(min_length=1, max_length=100)
    real_name: str = Field(min_length=1, max_length=100)
    email: EmailStr
    phone_number: str = Field(min_length=5, max_length=32)


class ReviewDecisionRequest(BaseModel):
    decision: Literal["APPROVED", "REJECTED"]
    reason: str | None = None

    @model_validator(mode="after")
    def rejected_requires_reason(self):
        if self.decision == "REJECTED" and not (self.reason and self.reason.strip()):
            raise ValueError("拒绝审核时必须填写原因")
        return self


class TeacherCreateRequest(BaseModel):
    teacher_no: str = Field(min_length=1, max_length=100)
    real_name: str = Field(min_length=1, max_length=100)
    email: EmailStr
    phone_number: str = Field(min_length=5, max_length=32)
    temporary_password: str = Field(min_length=10, max_length=256)


class UserPatchRequest(BaseModel):
    login_name: str | None = Field(default=None, min_length=1, max_length=100)
    real_name: str | None = Field(default=None, min_length=1, max_length=100)
    status: Literal["ACTIVATED", "DEACTIVATED"] | None = None


class ResetPasswordRequest(BaseModel):
    temporary_password: str = Field(min_length=10, max_length=256)


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
