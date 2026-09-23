from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response

from app.core.contracts import Page, Pagination
from app.deps import Identity, current_identity, get_auth_service, get_session, require_csrf, roles
from app.modules.auth.schemas import ResetPasswordRequest
from app.modules.auth.service import AuthService
from . import service
from .schemas import (
    ApplicationResponse,
    ApplicationUpdateRequest,
    ReviewDecisionRequest,
    ReviewPublic,
    TeacherCreateRequest,
    UserPatchRequest,
    UserPublic,
    UserResponse,
)
from .types import ReviewStatus, UserStatus, UserType

router = APIRouter(tags=["身份与审核"])
admin = roles(UserType.ADMIN)
staff = roles(UserType.ADMIN, UserType.TEACHER)


@router.get("/api/student/application", response_model=ApplicationResponse)
async def application(identity: Identity = Depends(current_identity), session=Depends(get_session)):
    """查询本人最近一次注册审核。"""
    return await service.get_application(session, identity)


@router.put(
    "/api/student/application",
    response_model=ApplicationResponse,
    dependencies=[Depends(require_csrf)],
)
async def resubmit(
    payload: ApplicationUpdateRequest,
    identity: Identity = Depends(current_identity),
    session=Depends(get_session),
):
    """拒绝后修改资料并重新提交申请。"""
    return await service.resubmit_application(session, identity, payload)


@router.get("/api/staff/reviews", response_model=Page[ReviewPublic])
async def reviews(
    status: ReviewStatus | None = Query(default=None),
    pagination: Pagination = Depends(),
    identity: Identity = Depends(staff),
    session=Depends(get_session),
):
    """分页检索学生注册审核。"""
    return await service.list_reviews(session, identity, pagination, status)


@router.post(
    "/api/staff/reviews/{review_id}/decision",
    response_model=ApplicationResponse,
    dependencies=[Depends(require_csrf)],
)
async def decide(
    review_id: UUID,
    payload: ReviewDecisionRequest,
    identity: Identity = Depends(staff),
    session=Depends(get_session),
):
    """通过或拒绝待处理申请。"""
    return await service.decide_review(session, identity, review_id, payload)


@router.get("/api/staff/students", response_model=Page[UserPublic])
async def students(
    status: UserStatus | None = None,
    pagination: Pagination = Depends(),
    identity: Identity = Depends(staff),
    session=Depends(get_session),
):
    """分页查询学生账号。"""
    return await service.list_users(session, identity, pagination, UserType.STUDENT, status)


@router.get("/api/admin/users", response_model=Page[UserPublic])
async def users(
    user_type: UserType | None = None,
    status: UserStatus | None = None,
    pagination: Pagination = Depends(),
    identity: Identity = Depends(admin),
    session=Depends(get_session),
):
    """按角色、状态、姓名或登录名分页查询用户。"""
    return await service.list_users(session, identity, pagination, user_type, status)


@router.get("/api/admin/teachers", response_model=Page[UserPublic])
async def teachers(
    status: UserStatus | None = None,
    pagination: Pagination = Depends(),
    identity: Identity = Depends(admin),
    session=Depends(get_session),
):
    """分页查询可供班级关联的教师。"""
    return await service.list_users(session, identity, pagination, UserType.TEACHER, status)


@router.post(
    "/api/admin/teachers",
    status_code=201,
    response_model=UserResponse,
    dependencies=[Depends(require_csrf)],
)
async def create_teacher(
    payload: TeacherCreateRequest, identity: Identity = Depends(admin), session=Depends(get_session)
):
    """创建首次登录必须改密的教师账号。"""
    return await service.create_teacher(session, identity, payload)


@router.patch(
    "/api/admin/users/{user_id}", response_model=UserResponse, dependencies=[Depends(require_csrf)]
)
async def patch_user(
    user_id: UUID,
    payload: UserPatchRequest,
    response: Response,
    identity: Identity = Depends(admin),
    auth: AuthService = Depends(get_auth_service),
):
    """更正身份资料或改变账号启用状态。"""
    result, complete = await auth.update_user(identity, user_id, payload)
    response.headers["X-Session-Cleanup"] = "complete" if complete else "pending"
    return result


@router.post(
    "/api/admin/users/{user_id}/reset-password",
    status_code=204,
    dependencies=[Depends(require_csrf)],
)
async def reset_password(
    user_id: UUID,
    payload: ResetPasswordRequest,
    response: Response,
    identity: Identity = Depends(admin),
    auth: AuthService = Depends(get_auth_service),
):
    """分配临时密码并使旧认证版本失效。"""
    complete = await auth.reset_password(identity, user_id, payload.temporary_password)
    response.headers["X-Session-Cleanup"] = "complete" if complete else "pending"
