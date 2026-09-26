from uuid import UUID
from pydantic import BaseModel


class AssetPublic(BaseModel):
    id: UUID
    url: str
    original_name: str
    media_type: str
    size_bytes: int
