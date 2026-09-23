from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import Column, DateTime, Index, Text
from sqlmodel import Field, SQLModel

from app.core.clock import utc_now


class SessionCleanup(SQLModel, table=True):
    """与业务写入同事务保存的幂等清理任务，不保存任何凭据。"""

    __tablename__ = "session_cleanup"
    __table_args__ = (Index("ix_session_cleanup_pending", "completed_at", "created_at"),)

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    user_id: UUID = Field(foreign_key="user_account.id")
    revoke_before_version: int | None = None
    clear_password_rate: bool = False
    attempts: int = 0
    last_error: str | None = Field(default=None, sa_column=Column(Text))
    created_at: datetime = Field(default_factory=utc_now, sa_type=DateTime(timezone=True))
    last_attempt_at: datetime | None = Field(default=None, sa_type=DateTime(timezone=True))
    completed_at: datetime | None = Field(default=None, sa_type=DateTime(timezone=True))
