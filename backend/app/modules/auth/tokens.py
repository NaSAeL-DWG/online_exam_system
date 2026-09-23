from datetime import datetime, timedelta, timezone
from uuid import UUID
import jwt
from app.config import Settings


def _access_token(settings: Settings, user_id: UUID, session_id: UUID) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "sid": str(session_id),
        "iat": now,
        "exp": now + timedelta(minutes=settings.access_minutes),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


def issue_access_token(settings: Settings, user_id: UUID, session_id: UUID) -> str:
    """为已存在的会话签发短期 Access JWT。"""

    return _access_token(settings, user_id, session_id)


def decode_access(settings: Settings, value: str) -> tuple[UUID, UUID]:
    payload = jwt.decode(value, settings.jwt_secret, algorithms=["HS256"])
    return UUID(payload["sub"]), UUID(payload["sid"])
