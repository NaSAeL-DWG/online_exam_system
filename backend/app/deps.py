from fastapi import Cookie, Depends, Header, Request

from app.errors import api_error
from app.modules.auth.service import AuthService, authenticate
from app.modules.identity.service import ensure_role
from app.modules.identity.types import Identity, UserType


async def get_session(request: Request):
    async with request.app.state.resources.session_factory() as session:
        yield session


async def get_auth_service(request: Request, session=Depends(get_session)):
    resources = request.app.state.resources
    return AuthService(
        session, resources.session_factory, resources.redis, request.app.state.settings
    )


async def require_csrf(
    request: Request,
    csrf_cookie: str | None = Cookie(default=None, alias="csrf_token"),
    csrf_header: str | None = Header(default=None, alias="X-CSRF-Token"),
):
    """校验双提交 CSRF Token。"""
    if not csrf_cookie or not csrf_header or csrf_cookie != csrf_header:
        raise api_error(403, "CSRF_INVALID", "CSRF 校验失败")


async def current_identity(
    request: Request, access_token: str | None = Cookie(default=None)
) -> Identity:
    """独立读事务返回不可变快照，避免向写用例带入 autobegin 或 ORM 缓存。"""
    resources = request.app.state.resources
    async with resources.session_factory() as session:
        return await authenticate(
            session, resources.redis, request.app.state.settings, access_token
        )


async def active_identity(identity: Identity = Depends(current_identity)) -> Identity:
    ensure_role(identity.user)
    return identity


def roles(*allowed: UserType):
    async def dependency(identity: Identity = Depends(active_identity)) -> Identity:
        ensure_role(identity.user, *allowed)
        return identity

    return dependency
