from dataclasses import dataclass
from uuid import UUID

import jwt
from fastapi import Cookie, Depends, Header, Request
from redis.exceptions import RedisError
from sqlalchemy.ext.asyncio import AsyncSession

from .errors import api_error
from .models import User, UserStatus, UserType
from .security import decode_access, touch_session


async def get_session(request: Request):
    async with request.app.state.resources.session_factory() as session:
        yield session


async def require_csrf(
    request: Request,
    csrf_cookie: str | None = Cookie(default=None, alias="csrf_token"),
    csrf_header: str | None = Header(default=None, alias="X-CSRF-Token"),
) -> None:
    """校验双提交 CSRF Token。"""

    if not csrf_cookie or not csrf_header or csrf_cookie != csrf_header:
        raise api_error(403, "CSRF_INVALID", "CSRF 校验失败")


@dataclass(slots=True)
class Identity:
    user: User
    session_id: UUID


async def current_identity(
    request: Request,
    session: AsyncSession = Depends(get_session),
    access_token: str | None = Cookie(default=None),
) -> Identity:
    """校验 JWT、Redis 会话和数据库账号状态版本。"""

    if not access_token:
        raise api_error(401, "AUTH_REQUIRED", "请先登录")
    try:
        user_id, session_id = decode_access(request.app.state.settings, access_token)
        values = await touch_session(
            request.app.state.resources.redis, request.app.state.settings, session_id
        )
    except (jwt.PyJWTError, ValueError):
        raise api_error(401, "SESSION_INVALID", "登录已失效") from None
    except RedisError:
        raise api_error(503, "AUTH_SERVICE_UNAVAILABLE", "认证服务暂时不可用，请重试") from None
    if not values or values.get("user_id") != str(user_id):
        raise api_error(401, "SESSION_INVALID", "登录已失效")
    user = await session.get(User, user_id)
    if not user or user.status == UserStatus.DEACTIVATED:
        raise api_error(403, "ACCOUNT_DEACTIVATED", "账号已停用")
    if int(values.get("auth_version", -1)) != user.auth_version:
        raise api_error(401, "SESSION_INVALID", "登录已失效")
    return Identity(user, session_id)


async def active_identity(identity: Identity = Depends(current_identity)) -> Identity:
    """要求已激活且已完成首次改密。"""

    if identity.user.must_change_password:
        raise api_error(403, "PASSWORD_CHANGE_REQUIRED", "请先修改临时密码")
    if identity.user.status != UserStatus.ACTIVATED:
        raise api_error(403, "ACCOUNT_NOT_ACTIVE", "账号尚未激活")
    return identity


def roles(*allowed: UserType):
    async def dependency(identity: Identity = Depends(active_identity)) -> Identity:
        if identity.user.user_type not in allowed:
            raise api_error(403, "FORBIDDEN", "没有执行此操作的权限")
        return identity

    return dependency
