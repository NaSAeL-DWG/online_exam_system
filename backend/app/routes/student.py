from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from ..deps import Identity, current_identity, get_session, require_csrf
from ..errors import api_error
from ..models import (
    AuditEvent,
    RegistrationReview,
    ReviewStatus,
    StudentProfile,
    User,
    UserType,
    utc_now,
)
from ..schemas import ApplicationPublic, ApplicationUpdateRequest

router = APIRouter(prefix="/api/student", tags=["学生申请"])


async def _latest_application(session: AsyncSession, user_id):
    return await session.scalar(
        select(RegistrationReview)
        .where(RegistrationReview.user_id == user_id)
        .order_by(RegistrationReview.submitted_at.desc())
        .limit(1)
    )


@router.get("/application")
async def get_application(
    identity: Identity = Depends(current_identity), session: AsyncSession = Depends(get_session)
):
    """查询当前学生最近一次注册审核申请。"""

    if identity.user.user_type != UserType.STUDENT:
        raise api_error(403, "FORBIDDEN", "仅学生可查询注册申请")
    application = await _latest_application(session, identity.user.id)
    if not application:
        raise api_error(404, "APPLICATION_NOT_FOUND", "未找到注册申请")
    return {"application": ApplicationPublic.model_validate(application)}


@router.put("/application", dependencies=[Depends(require_csrf)])
async def resubmit_application(
    payload: ApplicationUpdateRequest,
    identity: Identity = Depends(current_identity),
    session: AsyncSession = Depends(get_session),
):
    """拒绝后修改身份资料并重新提交审核。"""

    if identity.user.user_type != UserType.STUDENT:
        raise api_error(403, "FORBIDDEN", "仅学生可重新提交申请")
    if identity.user.must_change_password:
        raise api_error(403, "PASSWORD_CHANGE_REQUIRED", "请先修改临时密码")
    user = await session.get(User, identity.user.id, with_for_update=True)
    latest = await _latest_application(session, user.id)
    if not latest or latest.status != ReviewStatus.REJECTED:
        raise api_error(409, "APPLICATION_NOT_REJECTED", "仅被拒绝的申请可以重新提交")
    profile = await session.get(StudentProfile, user.id)
    user.login_name = payload.student_no
    user.real_name = payload.real_name
    user.email = str(payload.email)
    user.phone_number = payload.phone_number
    user.updated_at = utc_now()
    profile.student_no = payload.student_no
    profile.updated_at = utc_now()
    application = RegistrationReview(
        user_id=user.id,
        submitted_profile={
            "student_no": payload.student_no,
            "real_name": payload.real_name,
            "email": str(payload.email),
            "phone_number": payload.phone_number,
        },
    )
    session.add(application)
    session.add(
        AuditEvent(
            actor_id=user.id,
            action="REGISTRATION_RESUBMITTED",
            entity_type="registration_review",
            entity_id=application.id,
            after_data={"student_no": payload.student_no},
        )
    )
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise api_error(409, "LOGIN_NAME_EXISTS", "登录账号已存在") from None
    await session.refresh(application)
    return {"application": ApplicationPublic.model_validate(application)}
