from datetime import datetime
from typing import Literal
from uuid import UUID
from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator
from .models import ReviewStatus, UserStatus, UserType


class UserPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True, frozen=True)

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


class SubmittedProfile(BaseModel):
    student_no: str
    real_name: str
    email: str
    phone_number: str


class ApplicationPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    status: ReviewStatus
    reason: str | None
    submitted_profile: SubmittedProfile
    submitted_at: datetime
    reviewed_at: datetime | None
    reviewer_id: UUID | None


class RegisterRequest(BaseModel):
    student_no: str = Field(min_length=1, max_length=100)
    real_name: str = Field(min_length=1, max_length=100)
    email: EmailStr
    phone_number: str = Field(min_length=5, max_length=32)
    password: str = Field(min_length=10, max_length=256)


class RegistrationResponse(BaseModel):
    user: UserPublic
    application: ApplicationPublic


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


class UserResponse(BaseModel):
    user: UserPublic


class ApplicationResponse(BaseModel):
    application: ApplicationPublic


class ReviewPublic(ApplicationPublic):
    user: UserSummary
