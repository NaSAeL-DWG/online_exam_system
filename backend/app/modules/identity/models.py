from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    Index,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlmodel import Field, SQLModel


from app.core.clock import utc_now


class UserType(StrEnum):
    STUDENT = "STUDENT"
    TEACHER = "TEACHER"
    ADMIN = "ADMIN"


class UserStatus(StrEnum):
    WAITING_ACTIVATE = "WAITING_ACTIVATE"
    ACTIVATED = "ACTIVATED"
    DEACTIVATED = "DEACTIVATED"


class ReviewStatus(StrEnum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class User(SQLModel, table=True):
    __tablename__ = "user_account"
    __table_args__ = (
        UniqueConstraint("login_name"),
        Index("ix_user_account_login_name", "login_name"),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    login_name: str = Field(max_length=100)
    password_hash: str = Field(sa_column=Column(Text, nullable=False))
    phone_number: str = Field(max_length=32)
    email: str = Field(max_length=320)
    real_name: str = Field(max_length=100)
    user_type: UserType = Field(
        sa_column=Column(SAEnum(UserType, name="user_type"), nullable=False)
    )
    status: UserStatus = Field(
        sa_column=Column(SAEnum(UserStatus, name="user_status"), nullable=False)
    )
    email_verified_at: datetime | None = Field(default=None, sa_type=DateTime(timezone=True))
    phone_verified_at: datetime | None = Field(default=None, sa_type=DateTime(timezone=True))
    must_change_password: bool = False
    auth_version: int = Field(default=0, sa_type=BigInteger)
    created_at: datetime = Field(default_factory=utc_now, sa_type=DateTime(timezone=True))
    updated_at: datetime = Field(default_factory=utc_now, sa_type=DateTime(timezone=True))


class StudentProfile(SQLModel, table=True):
    __tablename__ = "student_profile"

    user_id: UUID = Field(
        sa_column=Column(PGUUID(as_uuid=True), ForeignKey("user_account.id"), primary_key=True)
    )
    student_no: str = Field(unique=True, max_length=100)
    created_at: datetime = Field(default_factory=utc_now, sa_type=DateTime(timezone=True))
    updated_at: datetime = Field(default_factory=utc_now, sa_type=DateTime(timezone=True))


class TeacherProfile(SQLModel, table=True):
    __tablename__ = "teacher_profile"

    user_id: UUID = Field(
        sa_column=Column(PGUUID(as_uuid=True), ForeignKey("user_account.id"), primary_key=True)
    )
    teacher_no: str = Field(unique=True, max_length=100)
    created_at: datetime = Field(default_factory=utc_now, sa_type=DateTime(timezone=True))
    updated_at: datetime = Field(default_factory=utc_now, sa_type=DateTime(timezone=True))


class RegistrationReview(SQLModel, table=True):
    __tablename__ = "registration_review"
    __table_args__ = (
        Index("ix_registration_review_user_status", "user_id", "status"),
        Index(
            "uq_registration_review_pending_user",
            "user_id",
            unique=True,
            postgresql_where=text("status = 'PENDING'::review_status"),
        ),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    user_id: UUID = Field(foreign_key="user_account.id")
    status: ReviewStatus = Field(
        default=ReviewStatus.PENDING,
        sa_column=Column(SAEnum(ReviewStatus, name="review_status"), nullable=False),
    )
    submitted_profile: dict[str, Any] = Field(sa_column=Column(JSONB, nullable=False))
    reviewer_id: UUID | None = Field(default=None, foreign_key="user_account.id")
    reason: str | None = Field(default=None, sa_column=Column(Text))
    submitted_at: datetime = Field(default_factory=utc_now, sa_type=DateTime(timezone=True))
    reviewed_at: datetime | None = Field(default=None, sa_type=DateTime(timezone=True))


class AuditEvent(SQLModel, table=True):
    __tablename__ = "audit_event"
    __table_args__ = (
        Index("ix_audit_event_entity", "entity_type", "entity_id", "created_at"),
        Index(
            "ix_audit_event_unpublished",
            "created_at",
            "id",
            postgresql_where=text("log_published = false"),
        ),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    actor_id: UUID | None = Field(default=None, foreign_key="user_account.id")
    action: str = Field(max_length=100, index=True)
    entity_type: str = Field(max_length=100)
    entity_id: UUID
    reason: str | None = Field(default=None, sa_column=Column(Text))
    before_data: dict[str, Any] | None = Field(default=None, sa_column=Column(JSONB))
    after_data: dict[str, Any] | None = Field(default=None, sa_column=Column(JSONB))
    created_at: datetime = Field(default_factory=utc_now, sa_type=DateTime(timezone=True))
    log_published: bool = Field(
        default=False, sa_column=Column(Boolean, nullable=False, server_default=text("false"))
    )


class AuditPublication(SQLModel, table=True):
    """已提交审计的可见顺序，避免事件时间或事务内序号先于提交而跳漏。"""

    __tablename__ = "audit_publication"

    id: int | None = Field(default=None, sa_column=Column(BigInteger, primary_key=True))
    event_id: UUID = Field(foreign_key="audit_event.id", unique=True)


class AuditPublicationState(SQLModel, table=True):
    __tablename__ = "audit_publication_state"

    id: int = Field(default=1, primary_key=True)
