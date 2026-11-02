from datetime import datetime

from sqlalchemy import BigInteger, Column, DateTime, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel

from app.core.clock import utc_now


class RuntimeLog(SQLModel, table=True):
    __tablename__ = "runtime_log"

    id: int | None = Field(default=None, sa_column=Column(BigInteger, primary_key=True))
    timestamp: datetime = Field(default_factory=utc_now, sa_type=DateTime(timezone=True))
    level: str = Field(max_length=10)
    module: str = Field(max_length=100, index=True)
    task: str = Field(max_length=100)
    message: str = Field(sa_column=Column(Text, nullable=False))
    correlation_id: str | None = Field(default=None, max_length=100, index=True)


class LogSettings(SQLModel, table=True):
    __tablename__ = "log_settings"

    id: int = Field(default=1, primary_key=True)
    file_enabled: bool = False
    debug_modules: dict[str, str] = Field(
        default_factory=dict, sa_column=Column(JSONB, nullable=False)
    )
