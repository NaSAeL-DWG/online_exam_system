import hashlib
import secrets
import time
from dataclasses import dataclass
from uuid import UUID, uuid4
from redis.asyncio import Redis
from app.config import Settings
from .tokens import issue_access_token


def token_digest(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


_RATE_LIMIT_SCRIPT = """
local count = redis.call('INCR', KEYS[1])
if count == 1 then redis.call('EXPIRE', KEYS[1], tonumber(ARGV[1])) end
return count
"""


async def consume_rate_limit(redis: Redis, key: str, limit: int, window_seconds: int) -> bool:
    """原子增加限流计数；返回本次请求是否允许继续。"""

    count = await redis.eval(_RATE_LIMIT_SCRIPT, 1, key, str(window_seconds))
    return int(count) <= limit


@dataclass(slots=True)
class SessionTokens:
    session_id: UUID
    access_token: str
    refresh_token: str


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
    return SessionTokens(
        session_id, issue_access_token(settings, user_id, session_id), refresh_token
    )


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


async def touch_session(
    redis: Redis, settings: Settings, session_id: UUID
) -> dict[str, str] | None:
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
if redis.call('HGET', key, 'auth_version') ~= ARGV[5] then return 0 end
if tonumber(redis.call('HGET', key, 'absolute_expires_at')) <= tonumber(ARGV[3]) then
  redis.call('DEL', key); return 0
end
if redis.call('HGET', key, 'refresh_hash') ~= ARGV[1] then return -1 end
redis.call('HSET', key, 'refresh_hash', ARGV[2], 'last_active_at', ARGV[3])
redis.call('EXPIRE', key, tonumber(ARGV[4]))
return 1
"""


async def rotate_refresh(
    redis: Redis, settings: Settings, session_id: UUID, presented: str, values: dict[str, str]
) -> tuple[str, dict[str, str]] | None:
    """以 Redis 原子脚本消费旧刷新凭据并写入新摘要。"""

    key = f"session:{session_id}"
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
        values["auth_version"],
    )
    if result != 1:
        if result == -1:
            await redis.delete(key)
        return None
    return replacement, values


async def read_session(redis, session_id):
    return await redis.hgetall(f"session:{session_id}")


async def limit_login(redis, remote, login_name):
    return await consume_rate_limit(redis, f"login_rate:{remote}:{login_name}", 10, 60)


async def clear_login_rate(redis, remote, login_name):
    await redis.delete(f"login_rate:{remote}:{login_name}")


async def limit_password(redis, user_id):
    return await consume_rate_limit(redis, f"password_verify:{user_id}", 5, 60)


async def clear_password_rate(redis, user_id):
    await redis.delete(f"password_verify:{user_id}")


_REVOKE_OLD_SCRIPT = """
local version = redis.call('HGET', KEYS[1], 'auth_version')
if not version then redis.call('SREM', KEYS[2], ARGV[1]); return 0 end
if tonumber(version) < tonumber(ARGV[2]) then
  redis.call('DEL', KEYS[1])
  redis.call('SREM', KEYS[2], ARGV[1])
  return 1
end
return 0
"""


async def revoke_before_version(redis, user_id, version):
    """按版本原子删除旧会话，迟到的补偿不影响新密码建立的会话。"""
    index = f"user_sessions:{user_id}"
    for sid in await redis.smembers(index):
        await redis.eval(_REVOKE_OLD_SCRIPT, 2, f"session:{sid}", index, sid, str(version))


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
