import logging
from dataclasses import dataclass
from uuid import UUID

import jwt
from redis.exceptions import RedisError
from sqlalchemy.exc import SQLAlchemyError

from app.core.errors import BusinessError
from app.modules.identity import service as identity_service
from app.modules.identity.schemas import UserResponse
from app.modules.identity.types import Identity, UserStatus, UserType
from . import cleanup, session_store
from .password import hash_password, verify_password
from .tokens import decode_access, issue_access_token

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AuthenticationResult:
    payload: UserResponse
    tokens: session_store.SessionTokens


def unavailable():
    return BusinessError("AUTH_SERVICE_UNAVAILABLE", "认证服务暂时不可用，请重试")


async def authenticate(session, redis, settings, access_token):
    if not access_token:
        raise BusinessError("AUTH_REQUIRED", "请先登录")
    try:
        user_id, session_id = decode_access(settings, access_token)
        values = await session_store.touch_session(redis, settings, session_id)
    except (jwt.PyJWTError, ValueError):
        raise BusinessError("SESSION_INVALID", "登录已失效") from None
    except RedisError:
        raise unavailable() from None
    if not values or values.get("user_id") != str(user_id):
        raise BusinessError("SESSION_INVALID", "登录已失效")
    credentials = await identity_service.credentials_by_id(session, user_id)
    if credentials is None or credentials.auth_version != int(values.get("auth_version", -1)):
        raise BusinessError("SESSION_INVALID", "登录已失效")
    if credentials.user.status == UserStatus.DEACTIVATED:
        raise BusinessError("ACCOUNT_DEACTIVATED", "账号已停用")
    return Identity(credentials.user, session_id, credentials.auth_version)


async def login(session, redis, settings, payload, remote):
    try:
        if not await session_store.limit_login(redis, remote, payload.login_name):
            raise BusinessError("LOGIN_RATE_LIMITED", "登录尝试过于频繁")
        async with session.begin():
            credentials = await identity_service.credentials_by_login(
                session, payload.login_name, lock=True
            )
            if credentials is None or not await verify_password(
                credentials.password_hash, payload.password
            ):
                raise BusinessError("INVALID_CREDENTIALS", "账号或密码错误")
            if credentials.user.status == UserStatus.DEACTIVATED:
                raise BusinessError("ACCOUNT_DEACTIVATED", "账号已停用")
            await session_store.clear_login_rate(redis, remote, payload.login_name)
            tokens = await session_store.create_session(
                redis, settings, credentials.user.id, credentials.auth_version
            )
        return AuthenticationResult(UserResponse(user=credentials.user), tokens)
    except RedisError:
        raise unavailable() from None


async def refresh(session, redis, settings, refresh_token):
    """数据库前置检查完成后才 CAS；成功响应丢失时旧凭据重放使会话失效，须重新登录。"""
    rotated = False
    try:
        try:
            sid_text, raw_token = (refresh_token or "").split(".", 1)
            sid = UUID(sid_text)
        except ValueError:
            raise BusinessError("SESSION_INVALID", "登录已失效") from None
        values = await session_store.read_session(redis, sid)
        if not values:
            raise BusinessError("SESSION_INVALID", "登录已失效")
        # 持用户行锁覆盖最终 CAS，与停用/重置形成明确先后关系。
        await session.begin()
        credentials = await identity_service.credentials_by_id(
            session, UUID(values["user_id"]), lock=True
        )
        if (
            credentials is None
            or credentials.user.status == UserStatus.DEACTIVATED
            or credentials.auth_version != int(values["auth_version"])
        ):
            raise BusinessError("SESSION_INVALID", "登录已失效")
        response = UserResponse(user=credentials.user)
        access = issue_access_token(settings, credentials.user.id, sid)
        result = await session_store.rotate_refresh(redis, settings, sid, raw_token, values)
        if result is None:
            raise BusinessError("SESSION_INVALID", "登录已失效")
        rotated = True
        replacement, _ = result
        return AuthenticationResult(response, session_store.SessionTokens(sid, access, replacement))
    except RedisError:
        raise unavailable() from None
    finally:
        # 此事务只有锁读取，无写入。CAS 后释放锁失败不伪装成凭据尚未消费。
        if session.in_transaction():
            try:
                await session.rollback()
            except SQLAlchemyError:
                if not rotated:
                    raise
                logger.error("refresh_lock_release_failed_after_rotation")


async def logout(redis, identity):
    try:
        await session_store.revoke_session(redis, identity.session_id, identity.user.id)
    except RedisError:
        raise unavailable() from None


async def check_password_rate(redis, identity):
    try:
        if not await session_store.limit_password(redis, identity.user.id):
            raise BusinessError("PASSWORD_VERIFY_RATE_LIMITED", "密码验证尝试过于频繁")
    except RedisError:
        raise unavailable() from None


async def change_password(session, session_factory, redis, identity, payload):
    await check_password_rate(redis, identity)
    new_hash = await hash_password(payload.new_password)
    async with session.begin():
        version = await identity_service.replace_password(
            session, identity, payload.current_password, new_hash
        )
        task = cleanup.schedule(
            session, identity.user.id, revoke_before_version=version, clear_password_rate=True
        )
    return await cleanup.deliver(session_factory, redis, task.id)


async def change_contacts(session, session_factory, redis, identity, payload):
    if identity.user.must_change_password:
        raise BusinessError("PASSWORD_CHANGE_REQUIRED", "请先修改临时密码")
    await check_password_rate(redis, identity)
    async with session.begin():
        result = await identity_service.replace_contacts(session, identity, payload)
        task = cleanup.schedule(session, identity.user.id, clear_password_rate=True)
    complete = await cleanup.deliver(session_factory, redis, task.id)
    return result, complete


async def reset_password(
    session, session_factory, redis, user_id, password, *, identity=None, cli=False
):
    new_hash = await hash_password(password)
    async with session.begin():
        version = await identity_service.reset_password(
            session, user_id, new_hash, identity=identity, cli=cli
        )
        task = cleanup.schedule(
            session, user_id, revoke_before_version=version, clear_password_rate=True
        )
    return await cleanup.deliver(session_factory, redis, task.id)


async def update_user(session, session_factory, redis, identity, user_id, payload):
    result, task_id = await identity_service.patch_user(session, identity, user_id, payload)
    complete = await cleanup.deliver(session_factory, redis, task_id) if task_id else True
    return result, complete


async def reset_admin(session, session_factory, redis, login_name, password):
    credentials = await identity_service.credentials_by_login(session, login_name)
    if credentials is None or credentials.user.user_type != UserType.ADMIN:
        raise BusinessError("USER_NOT_FOUND", "管理员账号不存在")
    user_id = credentials.user.id
    # CLI 的查询也触发 autobegin；快照后明确结束读事务再进入写用例。
    await session.rollback()
    return await reset_password(session, session_factory, redis, user_id, password, cli=True)


class AuthService:
    """HTTP/CLI 统一入口；调用方无需知道 Redis Key 和操作顺序。"""

    def __init__(self, session, session_factory, redis, settings):
        self.session = session
        self.session_factory = session_factory
        self.redis = redis
        self.settings = settings

    async def login(self, payload, remote):
        return await login(self.session, self.redis, self.settings, payload, remote)

    async def refresh(self, token):
        return await refresh(self.session, self.redis, self.settings, token)

    async def logout(self, identity):
        return await logout(self.redis, identity)

    async def change_password(self, identity, payload):
        return await change_password(
            self.session, self.session_factory, self.redis, identity, payload
        )

    async def change_contacts(self, identity, payload):
        return await change_contacts(
            self.session, self.session_factory, self.redis, identity, payload
        )

    async def reset_password(self, identity, user_id, password):
        return await reset_password(
            self.session, self.session_factory, self.redis, user_id, password, identity=identity
        )

    async def update_user(self, identity, user_id, payload):
        return await update_user(
            self.session, self.session_factory, self.redis, identity, user_id, payload
        )
