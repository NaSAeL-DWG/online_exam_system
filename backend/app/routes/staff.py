from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..deps import Identity, get_session, require_csrf, roles
from ..errors import api_error
from ..models import AuditEvent, RegistrationReview, ReviewStatus, User, UserStatus, UserType, utc_now
from ..schemas import ApplicationPublic, ReviewDecisionRequest, UserPublic, UserSummary

router = APIRouter(prefix="/api/staff", tags=["教职工"])
staff_identity = roles(UserType.TEACHER, UserType.ADMIN)


@router.get("/reviews")
async def list_reviews(
    status: ReviewStatus | None = Query(default=None),
    _: Identity = Depends(staff_identity),
    session: AsyncSession = Depends(get_session),
):
    """分页前的第一版列表查询学生注册审核。"""

    statement = select(RegistrationReview, User).join(User, User.id == RegistrationReview.user_id)
    if status:
        statement = statement.where(RegistrationReview.status == status)
    rows = (await session.execute(statement.order_by(RegistrationReview.submitted_at.desc()))).all()
    items = [
        {
            **ApplicationPublic.model_validate(review).model_dump(),
            "user": UserSummary.model_validate(user),
        }
        for review, user in rows
    ]
    return {"items": items, "total": len(items)}


@router.post("/reviews/{review_id}/decision", dependencies=[Depends(require_csrf)])
async def decide_review(
    review_id: UUID,
    payload: ReviewDecisionRequest,
    identity: Identity = Depends(staff_identity),
    session: AsyncSession = Depends(get_session),
):
    """在事务锁内通过或拒绝一条待审核申请。"""

    review = await session.scalar(
        select(RegistrationReview)
        .where(RegistrationReview.id == review_id)
        .with_for_update()
    )
    if not review:
        raise api_error(404, "REVIEW_NOT_FOUND", "审核申请不存在")
    if review.status != ReviewStatus.PENDING:
        raise api_error(409, "REVIEW_ALREADY_DECIDED", "审核申请已处理")
    user = await session.get(User, review.user_id, with_for_update=True)
    review.status = ReviewStatus(payload.decision)
    review.reason = payload.reason.strip() if payload.reason else None
    review.reviewer_id = identity.user.id
    review.reviewed_at = utc_now()
    if review.status == ReviewStatus.APPROVED and user.status != UserStatus.DEACTIVATED:
        user.status = UserStatus.ACTIVATED
    session.add(
        AuditEvent(
            actor_id=identity.user.id,
            action="REGISTRATION_REVIEW_DECIDED",
            entity_type="registration_review",
            entity_id=review.id,
            reason=review.reason,
            after_data={"status": review.status.value},
        )
    )
    await session.commit()
    await session.refresh(review)
    return {"application": ApplicationPublic.model_validate(review)}


@router.get("/students")
async def list_students(
    status: UserStatus | None = Query(default=None),
    _: Identity = Depends(staff_identity),
    session: AsyncSession = Depends(get_session),
):
    """列出学生账号，供审核和班级维护使用。"""

    statement = select(User).where(User.user_type == UserType.STUDENT)
    if status:
        statement = statement.where(User.status == status)
    users = (await session.scalars(statement.order_by(User.created_at.desc()))).all()
    return {"items": [UserPublic.model_validate(user) for user in users], "total": len(users)}
