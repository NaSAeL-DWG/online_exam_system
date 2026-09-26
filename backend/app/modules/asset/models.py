from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime
from sqlmodel import Field, SQLModel

from app.core.clock import utc_now


class UploadedAsset(SQLModel, table=True):
    __tablename__ = "uploaded_asset"
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    uploader_id: UUID = Field(foreign_key="user_account.id")
    storage_key: str = Field(unique=True, max_length=100)
    original_name: str = Field(max_length=255)
    media_type: str = Field(max_length=100)
    size_bytes: int
    created_at: datetime = Field(default_factory=utc_now, sa_type=DateTime(timezone=True))
