from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator


class LogQuery(BaseModel):
    start: datetime | None = None
    end: datetime | None = None
    module: str | None = Field(default=None, max_length=100)
    task: str | None = Field(default=None, max_length=100)
    q: str | None = Field(default=None, max_length=300)
    correlation_id: str | None = Field(default=None, max_length=100)
    level: Literal["INFO", "WARNING", "ERROR", "DEBUG"] = "INFO"
    actor_id: UUID | None = None
    action: str | None = Field(default=None, max_length=100)
    entity_type: str | None = Field(default=None, max_length=100)
    entity_id: UUID | None = None
    page_size: int = Field(default=100, ge=1, le=100)
    before: str | None = Field(default=None, max_length=200)
    after: str | None = Field(default=None, max_length=200)

    @model_validator(mode="after")
    def valid_range(self):
        if self.before and self.after:
            raise ValueError("历史与增量游标不能同时使用")
        for value in (self.start, self.end):
            if value and value.tzinfo is None:
                raise ValueError("时间须含时区")
        if self.start and self.end and self.start > self.end:
            raise ValueError("开始时间不能晚于结束时间")
        return self


class RuntimeItem(BaseModel):
    id: str
    cursor: str
    timestamp: datetime
    level: str
    module: str
    task: str
    message: str
    correlation_id: str | None
    formatted: str


class AuditItem(BaseModel):
    id: str
    cursor: str
    timestamp: datetime
    actor_id: UUID | None
    actor_name: str | None
    action: str
    entity_type: str
    entity_id: UUID
    summary: str
    formatted: str


class RuntimePage(BaseModel):
    items: list[RuntimeItem]
    next_before: str | None
    latest_cursor: str | None
    has_more: bool


class AuditPage(BaseModel):
    items: list[AuditItem]
    next_before: str | None
    latest_cursor: str | None
    has_more: bool


class DebugModule(BaseModel):
    module: str
    expires_at: datetime


class SettingsPublic(BaseModel):
    file_enabled: bool
    runtime_limit: int
    retention_days: int | None
    file_max_bytes: int = 10 * 1024 * 1024
    file_count: int = 5
    debug_modules: list[DebugModule]


class FileUpdate(BaseModel):
    file_enabled: bool


class DebugUpdate(BaseModel):
    enabled: bool
