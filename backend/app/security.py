import asyncio
import hashlib
import secrets
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from redis.asyncio import Redis

from .config import Settings

_hasher = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=4)


async def hash_password(password: str) -> str:
    """在线程池中执行 Argon2id 哈希，避免阻塞事件循环。"""

    return await asyncio.to_thread(_hasher.hash, password)


async def verify_password(password_hash: str, password: str) -> bool:
    """在线程池中验证密码。"""

    try:
        return await asyncio.to_thread(_hasher.verify, password_hash, password)
    except VerifyMismatchError:
        return False


def token_digest(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


@dataclass(slots=True)
class SessionTokens:
    session_id: UUID
    access_token: str
    refresh_token: str


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


async def create_session(
    redis: Redis, settings: Settings, user_id: UUID, auth_version: int
) -> SessionTokens:
    """建立具有空闲和绝对期限的 Redis 会话。"""

    session_id = uuid4()
    refresh_token = secrets.token_urlsafe(48)
    now = int(time.time())
    key = f"session:{session_id}"
    mapping = {
            "user_id": str(user_id),
            "auth_version": str(auth_version),
            "created_at": str(now),
            "last_active_at": str(now),
            "absolute_expires_at": str(now + settings.session_absolute_seconds),
            "refresh_hash": token_digest(refresh_token),
    }
    async with redis.pipeline(transaction=True) as pipe:
        pipe.hset(key, mapping=mapping)
        pipe.expire(key, min(settings.session_idle_seconds, settings.session_absolute_seconds))
        pipe.sadd(f"user_sessions:{user_id}", str(session_id))
        pipe.expire(f"user_sessions:{user_id}", settings.session_absolute_seconds)
        await pipe.execute()
    return SessionTokens(session_id, _access_token(settings, user_id, session_id), refresh_token)


_TOUCH_SCRIPT = """
local key = KEYS[1]
if redis.call('EXISTS', key) == 0 then return {} end
local absolute = tonumber(redis.call('HGET', key, 'absolute_expires_at'))
local remaining = absolute - tonumber(ARGV[1])
if remaining <= 0 then redis.call('DEL', key); return {} end
local ttl = math.min(tonumber(ARGV[2]), remaining)
redis.call('HSET', key, 'last_active_at', ARGV[1])
redis.call('EXPIRE', key, ttl)
return redis.call('HGETALL', key)
"""


async def touch_session(redis: Redis, settings: Settings, session_id: UUID) -> dict[str, str] | None:
    """校验并延长会话空闲期限，不超过绝对期限。"""

    key = f"session:{session_id}"
    now = int(time.time())
    flattened = await redis.eval(
        _TOUCH_SCRIPT, 1, key, str(now), str(settings.session_idle_seconds)
    )
    if not flattened:
        return None
    return dict(zip(flattened[::2], flattened[1::2], strict=True))


_ROTATE_SCRIPT = """
local key = KEYS[1]
if redis.call('EXISTS', key) == 0 then return 0 end
if redis.call('HGET', key, 'refresh_hash') ~= ARGV[1] then return -1 end
redis.call('HSET', key, 'refresh_hash', ARGV[2], 'last_active_at', ARGV[3])
redis.call('EXPIRE', key, tonumber(ARGV[4]))
return 1
"""


async def rotate_refresh(
    redis: Redis, settings: Settings, session_id: UUID, presented: str
) -> tuple[str, dict[str, str]] | None:
    """以 Redis 原子脚本消费旧刷新凭据并写入新摘要。"""

    key = f"session:{session_id}"
    values = await redis.hgetall(key)
    if not values:
        return None
    now = int(time.time())
    remaining = int(values["absolute_expires_at"]) - now
    if remaining <= 0:
        await redis.delete(key)
        return None
    replacement = secrets.token_urlsafe(48)
    ttl = min(settings.session_idle_seconds, remaining)
    result = await redis.eval(
        _ROTATE_SCRIPT,
        1,
        key,
        token_digest(presented),
        token_digest(replacement),
        str(now),
        str(ttl),
    )
    if result != 1:
        if result == -1:
            await redis.delete(key)
        return None
    return replacement, values


async def revoke_session(redis: Redis, session_id: UUID, user_id: UUID | None = None) -> None:
    """撤销一个会话及其用户索引。"""

    await redis.delete(f"session:{session_id}")
    if user_id:
        await redis.srem(f"user_sessions:{user_id}", str(session_id))


async def revoke_all_sessions(redis: Redis, user_id: UUID) -> None:
    """撤销用户的全部会话。"""

    index = f"user_sessions:{user_id}"
    session_ids = await redis.smembers(index)
    if session_ids:
        await redis.delete(*(f"session:{item}" for item in session_ids))
    await redis.delete(index)


def decode_access(settings: Settings, value: str) -> tuple[UUID, UUID]:
    payload = jwt.decode(value, settings.jwt_secret, algorithms=["HS256"])
    return UUID(payload["sub"]), UUID(payload["sid"])
