from sqlalchemy import func, or_, select
from .models import AuditEvent, RegistrationReview, StudentProfile, TeacherProfile, User, UserType


async def user_by_id(session, user_id, *, lock=False):
    return await session.get(User, user_id, with_for_update=lock, populate_existing=lock)


async def user_by_login(session, login_name, *, lock=False):
    statement = select(User).where(User.login_name == login_name)
    if lock:
        statement = statement.with_for_update().execution_options(populate_existing=True)
    return await session.scalar(statement)


async def admin(session):
    return await session.scalar(select(User).where(User.user_type == UserType.ADMIN))


async def users_by_ids(session, user_ids):
    if not user_ids:
        return []
    return (await session.scalars(select(User).where(User.id.in_(user_ids)))).all()


async def shared_locked_users(session, user_ids):
    return (
        await session.scalars(
            select(User)
            .where(User.id.in_(user_ids))
            .order_by(User.id)
            .with_for_update(read=True)
            .execution_options(populate_existing=True)
        )
    ).all()


async def add_user(session, user, profile=None):
    session.add(user)
    await session.flush()
    if profile is not None:
        session.add(profile)


def add_review(session, review):
    session.add(review)


def add_audit(session, **values):
    session.add(AuditEvent(**values))


async def profile_for_user(session, user):
    model = StudentProfile if user.user_type == UserType.STUDENT else TeacherProfile
    return await session.get(model, user.id)


async def latest_review(session, user_id):
    return await session.scalar(
        select(RegistrationReview)
        .where(RegistrationReview.user_id == user_id)
        .order_by(RegistrationReview.submitted_at.desc(), RegistrationReview.id.desc())
        .limit(1)
    )


async def review_by_id(session, review_id, *, lock=False):
    return await session.get(
        RegistrationReview, review_id, with_for_update=lock, populate_existing=lock
    )


async def list_users(session, pagination, user_type=None, status=None):
    statement = select(User)
    if user_type:
        statement = statement.where(User.user_type == user_type)
    if status:
        statement = statement.where(User.status == status)
    if pagination.q.strip():
        term = "%" + pagination.q.strip() + "%"
        statement = statement.where(or_(User.login_name.ilike(term), User.real_name.ilike(term)))
    total = await session.scalar(select(func.count()).select_from(statement.subquery()))
    users = (
        await session.scalars(
            statement.order_by(User.created_at.desc(), User.id)
            .offset((pagination.page - 1) * pagination.page_size)
            .limit(pagination.page_size)
        )
    ).all()
    return users, total


async def list_reviews(session, pagination, status=None):
    statement = select(RegistrationReview, User).join(User, User.id == RegistrationReview.user_id)
    if status:
        statement = statement.where(RegistrationReview.status == status)
    if pagination.q.strip():
        term = "%" + pagination.q.strip() + "%"
        statement = statement.where(or_(User.login_name.ilike(term), User.real_name.ilike(term)))
    total = await session.scalar(select(func.count()).select_from(statement.subquery()))
    rows = (
        await session.execute(
            statement.order_by(RegistrationReview.submitted_at.desc(), RegistrationReview.id)
            .offset((pagination.page - 1) * pagination.page_size)
            .limit(pagination.page_size)
        )
    ).all()
    return rows, total
