from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from redis.exceptions import RedisError
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from ..deps import Identity, get_session, require_csrf, roles
from ..errors import api_error
from ..models import (
    AuditEvent,
    RegistrationReview,
    ReviewStatus,
    StudentProfile,
    TeacherProfile,
    User,
    UserStatus,
    UserType,
    utc_now,
)
from ..schemas import ResetPasswordRequest, TeacherCreateRequest, UserPatchRequest, UserPublic
from ..security import hash_password, revoke_all_sessions

router = APIRouter(prefix="/api/admin", tags=["管理员"])
admin_identity = roles(UserType.ADMIN)


@router.post("/teachers", status_code=201, dependencies=[Depends(require_csrf)])
async def create_teacher(
    payload: TeacherCreateRequest,
    identity: Identity = Depends(admin_identity),
    session: AsyncSession = Depends(get_session),
):
    """创建已激活、首次登录必须改密的教师账号。"""

    user = User(
        login_name=payload.teacher_no,
        password_hash=await hash_password(payload.temporary_password),
        real_name=payload.real_name,
        email=str(payload.email),
        phone_number=payload.phone_number,
        user_type=UserType.TEACHER,
        status=UserStatus.ACTIVATED,
        must_change_password=True,
    )
    try:
        session.add(user)
        await session.flush()
        session.add(TeacherProfile(user_id=user.id, teacher_no=payload.teacher_no))
        session.add(
            AuditEvent(
                actor_id=identity.user.id,
                action="TEACHER_CREATED",
                entity_type="user",
                entity_id=user.id,
                after_data={"teacher_no": payload.teacher_no},
            )
        )
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise api_error(409, "LOGIN_NAME_EXISTS", "登录账号已存在") from None
    await session.refresh(user)
    return {"user": UserPublic.model_validate(user)}


@router.get("/users")
async def list_users(
    user_type: UserType | None = Query(default=None),
    status: UserStatus | None = Query(default=None),
    _: Identity = Depends(admin_identity),
    session: AsyncSession = Depends(get_session),
):
    """按角色和状态查询账号。"""

    statement = select(User)
    if user_type:
        statement = statement.where(User.user_type == user_type)
    if status:
        statement = statement.where(User.status == status)
    users = (await session.scalars(statement.order_by(User.created_at.desc()))).all()
    return {"items": [UserPublic.model_validate(user) for user in users], "total": len(users)}


@router.get("/teachers")
async def list_teachers(
    status: UserStatus | None = Query(default=None),
    _: Identity = Depends(admin_identity),
    session: AsyncSession = Depends(get_session),
):
    """列出教师账号，供班级关联选择。"""

    statement = select(User).where(User.user_type == UserType.TEACHER)
    if status:
        statement = statement.where(User.status == status)
    users = (await session.scalars(statement.order_by(User.created_at.desc()))).all()
    return {"items": [UserPublic.model_validate(user) for user in users], "total": len(users)}


@router.patch("/users/{user_id}", dependencies=[Depends(require_csrf)])
async def patch_user(
    user_id: UUID,
    payload: UserPatchRequest,
    request: Request,
    identity: Identity = Depends(admin_identity),
    session: AsyncSession = Depends(get_session),
):
    """更正身份字段或停用、恢复非管理员账号。"""

    user = await session.get(User, user_id, with_for_update=True)
    if not user:
        raise api_error(404, "USER_NOT_FOUND", "用户不存在")
    requested_status = UserStatus(payload.status) if payload.status else None
    if user.user_type == UserType.ADMIN and requested_status == UserStatus.DEACTIVATED:
        raise api_error(409, "ADMIN_DEACTIVATION_FORBIDDEN", "管理员账号不能通过后台停用")
    before = {
        "login_name": user.login_name,
        "real_name": user.real_name,
        "status": user.status.value,
    }
    if payload.login_name is not None and payload.login_name != user.login_name:
        profile = (
            await session.get(StudentProfile, user.id)
            if user.user_type == UserType.STUDENT
            else await session.get(TeacherProfile, user.id)
        )
        user.login_name = payload.login_name
        if isinstance(profile, StudentProfile):
            profile.student_no = payload.login_name
        elif isinstance(profile, TeacherProfile):
            profile.teacher_no = payload.login_name
    if payload.real_name is not None:
        user.real_name = payload.real_name
    revoke = False
    if requested_status is not None and requested_status != user.status:
        restored_status = requested_status
        if requested_status == UserStatus.ACTIVATED and user.user_type == UserType.STUDENT:
            latest = await session.scalar(
                select(RegistrationReview)
                .where(RegistrationReview.user_id == user.id)
                .order_by(RegistrationReview.submitted_at.desc())
                .limit(1)
            )
            if not latest or latest.status != ReviewStatus.APPROVED:
                if user.status != UserStatus.DEACTIVATED:
                    raise api_error(409, "REVIEW_REQUIRED", "学生尚未通过审核")
                restored_status = UserStatus.WAITING_ACTIVATE
        user.status = restored_status
        user.auth_version += 1
        revoke = True
    user.updated_at = utc_now()
    session.add(
        AuditEvent(
            actor_id=identity.user.id,
            action="USER_UPDATED",
            entity_type="user",
            entity_id=user.id,
            before_data=before,
            after_data={
                "login_name": user.login_name,
                "real_name": user.real_name,
                "status": user.status.value,
            },
        )
    )
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise api_error(409, "LOGIN_NAME_EXISTS", "登录账号已存在") from None
    if revoke:
        try:
            await revoke_all_sessions(request.app.state.resources.redis, user.id)
        except RedisError:
            raise api_error(
                503, "AUTH_SERVICE_UNAVAILABLE", "账号已更新，认证服务暂时不可用"
            ) from None
    await session.refresh(user)
    return {"user": UserPublic.model_validate(user)}


@router.post(
    "/users/{user_id}/reset-password", status_code=204, dependencies=[Depends(require_csrf)]
)
async def reset_password(
    user_id: UUID,
    payload: ResetPasswordRequest,
    request: Request,
    identity: Identity = Depends(admin_identity),
    session: AsyncSession = Depends(get_session),
):
    """为非管理员分配临时密码并撤销其全部旧会话。"""

    user = await session.get(User, user_id, with_for_update=True)
    if not user:
        raise api_error(404, "USER_NOT_FOUND", "用户不存在")
    if user.user_type == UserType.ADMIN:
        raise api_error(409, "ADMIN_RESET_REQUIRES_CLI", "管理员密码必须通过本地运维命令重置")
    user.password_hash = await hash_password(payload.temporary_password)
    user.must_change_password = True
    user.auth_version += 1
    user.updated_at = utc_now()
    session.add(
        AuditEvent(
            actor_id=identity.user.id,
            action="PASSWORD_RESET",
            entity_type="user",
            entity_id=user.id,
        )
    )
    await session.commit()
    try:
        await revoke_all_sessions(request.app.state.resources.redis, user.id)
    except RedisError:
        raise api_error(503, "AUTH_SERVICE_UNAVAILABLE", "密码已重置，认证服务暂时不可用") from None
