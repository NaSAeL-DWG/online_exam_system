from dataclasses import dataclass
from uuid import UUID
from .models import ReviewStatus, UserStatus, UserType  # noqa: F401
from .schemas import UserPublic


@dataclass(frozen=True, slots=True)
class Identity:
    """脱离 ORM identity map 的认证快照；关键写入必须在锁内再校验。"""

    user: UserPublic
    session_id: UUID
    auth_version: int


@dataclass(frozen=True, slots=True)
class Credentials:
    user: UserPublic
    password_hash: str
    auth_version: int
