import secrets
from uuid import UUID

from fastapi import APIRouter, Cookie, Depends, Request, Response
from redis.exceptions import RedisError
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from ..deps import Identity, current_identity, get_session, require_csrf
from ..errors import api_error
from ..models import (
    AuditEvent,
    RegistrationReview,
    StudentProfile,
    User,
    UserStatus,
    UserType,
    utc_now,
)
from ..schemas import ApplicationPublic, ContactsRequest, LoginRequest, PasswordRequest, RegisterRequest, RegistrationResponse, UserPublic
from ..security import (
    create_session,
    consume_rate_limit,
    hash_password,
    issue_access_token,
    revoke_all_sessions,
    revoke_session,
    rotate_refresh,
    verify_password,
)

router = APIRouter(prefix="/api/auth", tags=["认证"])


def _set_auth_cookies(response: Response, request: Request, access: str, refresh: str, sid: UUID):
    settings = request.app.state.settings
    common = {"secure": settings.cookie_secure, "samesite": settings.cookie_samesite, "path": "/"}
    response.set_cookie(
        "access_token", access, httponly=True, max_age=settings.access_minutes * 60, **common
    )
    response.set_cookie(
        "refresh_token",
        f"{sid}.{refresh}",
        httponly=True,
        max_age=settings.session_absolute_seconds,
        **common,
    )


def _clear_auth_cookies(response: Response, request: Request):
    settings = request.app.state.settings
    response.delete_cookie("access_token", path="/", secure=settings.cookie_secure)
    response.delete_cookie("refresh_token", path="/", secure=settings.cookie_secure)


@router.get("/csrf")
async def issue_csrf(request: Request, response: Response):
    """签发双提交 CSRF Token，并写入可读 Cookie。"""

    token = request.cookies.get("csrf_token") or secrets.token_urlsafe(32)
    response.set_cookie(
        "csrf_token",
        token,
        httponly=False,
        secure=request.app.state.settings.cookie_secure,
        samesite=request.app.state.settings.cookie_samesite,
        path="/",
    )
    return {"csrf_token": token}


@router.post("/register", status_code=201, response_model=RegistrationResponse, dependencies=[Depends(require_csrf)])
async def register(
    payload: RegisterRequest,
    session: AsyncSession = Depends(get_session),
):
    """注册学生账号并创建待审核申请。"""

    password_hash = await hash_password(payload.password)
    profile_snapshot = {
        "student_no": payload.student_no,
        "real_name": payload.real_name,
        "email": str(payload.email),
        "phone_number": payload.phone_number,
    }
    user = User(
        login_name=payload.student_no,
        password_hash=password_hash,
        phone_number=payload.phone_number,
        email=str(payload.email),
        real_name=payload.real_name,
        user_type=UserType.STUDENT,
        status=UserStatus.WAITING_ACTIVATE,
    )
    try:
        session.add(user)
        await session.flush()
        session.add(StudentProfile(user_id=user.id, student_no=payload.student_no))
        application = RegistrationReview(user_id=user.id, submitted_profile=profile_snapshot)
        session.add(application)
        session.add(
            AuditEvent(
                actor_id=user.id,
                action="REGISTRATION_SUBMITTED",
                entity_type="registration_review",
                entity_id=application.id,
                after_data={"student_no": payload.student_no},
            )
        )
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise api_error(409, "LOGIN_NAME_EXISTS", "登录账号已存在") from None
    await session.refresh(user)
    await session.refresh(application)
    return {"user": UserPublic.model_validate(user), "application": ApplicationPublic.model_validate(application)}


@router.post("/login", dependencies=[Depends(require_csrf)])
async def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    session: AsyncSession = Depends(get_session),
):
    """校验账号密码并建立 Redis 会话。"""

    redis = request.app.state.resources.redis
    rate_key = (
        f"login_rate:{request.client.host if request.client else 'unknown'}:{payload.login_name}"
    )
    try:
        if not await consume_rate_limit(redis, rate_key, 10, 60):
            raise api_error(429, "LOGIN_RATE_LIMITED", "登录尝试过于频繁")
    except RedisError:
        raise api_error(503, "AUTH_SERVICE_UNAVAILABLE", "认证服务暂时不可用，请重试") from None
    user = await session.scalar(select(User).where(User.login_name == payload.login_name))
    if not user or not await verify_password(user.password_hash, payload.password):
        raise api_error(401, "INVALID_CREDENTIALS", "账号或密码错误")
    if user.status == UserStatus.DEACTIVATED:
        raise api_error(403, "ACCOUNT_DEACTIVATED", "账号已停用")
    try:
        tokens = await create_session(redis, request.app.state.settings, user.id, user.auth_version)
        await redis.delete(rate_key)
    except RedisError:
        raise api_error(503, "AUTH_SERVICE_UNAVAILABLE", "认证服务暂时不可用，请重试") from None
    _set_auth_cookies(
        response, request, tokens.access_token, tokens.refresh_token, tokens.session_id
    )
    return {"user": UserPublic.model_validate(user)}


@router.post("/refresh", dependencies=[Depends(require_csrf)])
async def refresh(
    request: Request,
    response: Response,
    refresh_token: str | None = Cookie(default=None),
    session: AsyncSession = Depends(get_session),
):
    """原子消费刷新凭据并轮换 Cookie。"""

    try:
        sid_text, raw_token = (refresh_token or "").split(".", 1)
        sid = UUID(sid_text)
        rotated = await rotate_refresh(
            request.app.state.resources.redis, request.app.state.settings, sid, raw_token
        )
    except RedisError:
        raise api_error(503, "AUTH_SERVICE_UNAVAILABLE", "认证服务暂时不可用，请重试") from None
    except ValueError:
        rotated = None
    if not rotated:
        _clear_auth_cookies(response, request)
        raise api_error(401, "SESSION_INVALID", "登录已失效")
    replacement, values = rotated
    user = await session.get(User, UUID(values["user_id"]))
    if (
        not user
        or user.status == UserStatus.DEACTIVATED
        or user.auth_version != int(values["auth_version"])
    ):
        await revoke_session(request.app.state.resources.redis, sid)
        raise api_error(401, "SESSION_INVALID", "登录已失效")
    access = issue_access_token(request.app.state.settings, user.id, sid)
    _set_auth_cookies(response, request, access, replacement, sid)
    return {"user": UserPublic.model_validate(user)}


@router.post("/logout", status_code=204, dependencies=[Depends(require_csrf)])
async def logout(
    request: Request, response: Response, identity: Identity = Depends(current_identity)
):
    """撤销当前会话并清理认证 Cookie。"""

    try:
        await revoke_session(
            request.app.state.resources.redis, identity.session_id, identity.user.id
        )
    except RedisError:
        raise api_error(503, "AUTH_SERVICE_UNAVAILABLE", "认证服务暂时不可用，请重试") from None
    _clear_auth_cookies(response, request)


@router.get("/me")
async def me(identity: Identity = Depends(current_identity)):
    """返回当前登录用户的安全公开资料。"""

    return {"user": UserPublic.model_validate(identity.user)}


@router.put("/password", status_code=204, dependencies=[Depends(require_csrf)])
async def change_password(
    payload: PasswordRequest,
    request: Request,
    identity: Identity = Depends(current_identity),
    session: AsyncSession = Depends(get_session),
):
    """验证当前密码后更新密码并撤销全部旧会话。"""

    redis = request.app.state.resources.redis
    rate_key = f"password_verify:{identity.user.id}"
    try:
        if not await consume_rate_limit(redis, rate_key, 5, 60):
            raise api_error(429, "PASSWORD_VERIFY_RATE_LIMITED", "密码验证尝试过于频繁")
    except RedisError:
        raise api_error(503, "AUTH_SERVICE_UNAVAILABLE", "认证服务暂时不可用，请重试") from None
    user = await session.get(User, identity.user.id, with_for_update=True)
    if not user or not await verify_password(user.password_hash, payload.current_password):
        raise api_error(400, "CURRENT_PASSWORD_INVALID", "当前密码错误")
    user.password_hash = await hash_password(payload.new_password)
    user.must_change_password = False
    user.auth_version += 1
    user.updated_at = utc_now()
    session.add(
        AuditEvent(
            actor_id=user.id,
            action="PASSWORD_CHANGED",
            entity_type="user",
            entity_id=user.id,
        )
    )
    await session.commit()
    try:
        await redis.delete(rate_key)
        await revoke_all_sessions(redis, user.id)
    except RedisError:
        raise api_error(503, "AUTH_SERVICE_UNAVAILABLE", "认证服务暂时不可用，请重试") from None


@router.put("/contacts", dependencies=[Depends(require_csrf)])
async def change_contacts(
    payload: ContactsRequest,
    request: Request,
    identity: Identity = Depends(current_identity),
    session: AsyncSession = Depends(get_session),
):
    """验证当前密码后更新未验证的联系方式。"""

    if identity.user.must_change_password:
        raise api_error(403, "PASSWORD_CHANGE_REQUIRED", "请先修改临时密码")
    redis = request.app.state.resources.redis
    rate_key = f"password_verify:{identity.user.id}"
    try:
        if not await consume_rate_limit(redis, rate_key, 5, 60):
            raise api_error(429, "PASSWORD_VERIFY_RATE_LIMITED", "密码验证尝试过于频繁")
    except RedisError:
        raise api_error(503, "AUTH_SERVICE_UNAVAILABLE", "认证服务暂时不可用，请重试") from None
    user = await session.get(User, identity.user.id, with_for_update=True)
    if not user or not await verify_password(user.password_hash, payload.current_password):
        raise api_error(400, "CURRENT_PASSWORD_INVALID", "当前密码错误")
    old_contacts = {"email": user.email, "phone_number": user.phone_number}
    user.email = str(payload.email)
    user.phone_number = payload.phone_number
    user.updated_at = utc_now()
    session.add(
        AuditEvent(
            actor_id=user.id,
            action="CONTACTS_CHANGED",
            entity_type="user",
            entity_id=user.id,
            before_data=old_contacts,
            after_data={"email": user.email, "phone_number": user.phone_number},
        )
    )
    await session.commit()
    try:
        await redis.delete(rate_key)
    except RedisError:
        raise api_error(503, "AUTH_SERVICE_UNAVAILABLE", "认证服务暂时不可用，请重试") from None
    await session.refresh(user)
    return {"user": UserPublic.model_validate(user)}


@router.post("/verification/{channel}", dependencies=[Depends(require_csrf)])
async def verification_not_enabled(channel: str):
    """明确告知邮箱和手机号验证功能尚未启用。"""

    if channel not in {"email", "phone"}:
        raise api_error(404, "CHANNEL_NOT_FOUND", "未知验证渠道")
    raise api_error(501, "VERIFICATION_NOT_ENABLED", "验证功能尚未启用")
