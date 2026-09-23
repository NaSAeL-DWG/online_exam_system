import secrets
from uuid import UUID

from fastapi import APIRouter, Cookie, Depends, Request, Response

from app.deps import Identity, current_identity, get_auth_service, get_session, require_csrf
from app.errors import api_error
from app.modules.identity import service as identity_service
from app.modules.identity.schemas import RegisterRequest, RegistrationResponse, UserResponse
from .schemas import ContactsRequest, CsrfResponse, LoginRequest, PasswordRequest
from .service import AuthService

router = APIRouter(prefix="/api/auth", tags=["认证"])


def set_auth_cookies(response: Response, request: Request, access: str, refresh: str, sid: UUID):
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


def clear_auth_cookies(response, request):
    for name in ("access_token", "refresh_token"):
        response.delete_cookie(name, path="/", secure=request.app.state.settings.cookie_secure)


def cleanup_header(response, complete):
    response.headers["X-Session-Cleanup"] = "complete" if complete else "pending"


@router.get("/csrf", response_model=CsrfResponse)
async def csrf(request: Request, response: Response):
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
    return CsrfResponse(csrf_token=token)


@router.post(
    "/register",
    status_code=201,
    response_model=RegistrationResponse,
    dependencies=[Depends(require_csrf)],
)
async def register(payload: RegisterRequest, session=Depends(get_session)):
    """注册学生账号并提交审核申请。"""
    return await identity_service.register_student(session, payload)


@router.post("/login", response_model=UserResponse, dependencies=[Depends(require_csrf)])
async def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    auth: AuthService = Depends(get_auth_service),
):
    """登录并交付认证 Cookie。"""
    result = await auth.login(payload, request.client.host if request.client else "unknown")
    set_auth_cookies(
        response,
        request,
        result.tokens.access_token,
        result.tokens.refresh_token,
        result.tokens.session_id,
    )
    return result.payload


@router.post("/refresh", response_model=UserResponse, dependencies=[Depends(require_csrf)])
async def refresh(
    request: Request,
    response: Response,
    refresh_token: str | None = Cookie(default=None),
    auth: AuthService = Depends(get_auth_service),
):
    """完成一次刷新并交付新凭据；旧凭据不支持重放恢复。"""
    result = await auth.refresh(refresh_token)
    set_auth_cookies(
        response,
        request,
        result.tokens.access_token,
        result.tokens.refresh_token,
        result.tokens.session_id,
    )
    return result.payload


@router.post("/logout", status_code=204, dependencies=[Depends(require_csrf)])
async def logout(
    request: Request,
    response: Response,
    identity: Identity = Depends(current_identity),
    auth: AuthService = Depends(get_auth_service),
):
    """撤销当前会话并清理认证 Cookie。"""
    await auth.logout(identity)
    clear_auth_cookies(response, request)


@router.get("/me", response_model=UserResponse)
async def me(identity: Identity = Depends(current_identity)):
    """返回当前用户的公开身份快照。"""
    return UserResponse(user=identity.user)


@router.put("/password", status_code=204, dependencies=[Depends(require_csrf)])
async def change_password(
    payload: PasswordRequest,
    response: Response,
    identity: Identity = Depends(current_identity),
    auth: AuthService = Depends(get_auth_service),
):
    """修改密码，提交成功后准确返回清理完成或待补偿状态。"""
    cleanup_header(response, await auth.change_password(identity, payload))


@router.put("/contacts", response_model=UserResponse, dependencies=[Depends(require_csrf)])
async def change_contacts(
    payload: ContactsRequest,
    response: Response,
    identity: Identity = Depends(current_identity),
    auth: AuthService = Depends(get_auth_service),
):
    """验证当前密码后修改联系方式。"""
    result, complete = await auth.change_contacts(identity, payload)
    cleanup_header(response, complete)
    return result


@router.post("/verification/{channel}", dependencies=[Depends(require_csrf)], status_code=501)
async def verification_not_enabled(channel: str):
    """验证渠道为明确的未启用占位能力。"""
    if channel not in {"email", "phone"}:
        raise api_error(404, "CHANNEL_NOT_FOUND", "未知验证渠道")
    raise api_error(501, "VERIFICATION_NOT_ENABLED", "验证功能尚未启用")
