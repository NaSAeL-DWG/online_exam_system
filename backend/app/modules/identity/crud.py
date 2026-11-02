from sqlalchemy import String, and_, cast, func, literal, or_, select, update
from .models import (
    AuditEvent,
    AuditPublication,
    AuditPublicationState,
    RegistrationReview,
    StudentProfile,
    TeacherProfile,
    User,
    UserType,
)


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


async def matching_user_ids(session, user_ids, query):
    term = "%" + query.strip() + "%"
    return (
        await session.scalars(
            select(User.id).where(
                User.id.in_(user_ids), or_(User.real_name.ilike(term), User.login_name.ilike(term))
            )
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


async def audit_rows(session, query, cursor=None, *, export=False):
    """审计查询只按安全索引字段筛选，不允许通过原始 JSON 或原因探测敏感值。"""
    statement = (
        select(AuditEvent, User.user_type, AuditPublication.id)
        .join(AuditPublication, AuditPublication.event_id == AuditEvent.id)
        .outerjoin(User, User.id == AuditEvent.actor_id)
    )
    if export:
        # 不因投影补齐进度而静默少导，直接检查已提交原始审计的10001条上限。
        statement = select(AuditEvent, User.user_type, literal(0)).outerjoin(
            User, User.id == AuditEvent.actor_id
        )
    for name in ("actor_id", "action", "entity_type", "entity_id"):
        if value := getattr(query, name):
            statement = statement.where(getattr(AuditEvent, name) == value)
    if query.start:
        statement = statement.where(AuditEvent.created_at >= query.start)
    if query.end:
        statement = statement.where(AuditEvent.created_at <= query.end)
    if query.q:
        statement = statement.where(
            or_(
                AuditEvent.action.icontains(query.q, autoescape=True),
                AuditEvent.entity_type.icontains(query.q, autoescape=True),
                cast(AuditEvent.entity_id, String).icontains(query.q, autoescape=True),
                and_(
                    AuditEvent.action == "LOG_DEBUG_SETTINGS",
                    AuditEvent.after_data["module"].astext.icontains(query.q, autoescape=True),
                ),
            )
        )
    ascending = bool(query.after) and not export
    if cursor and not export:
        statement = statement.where(
            AuditPublication.id > cursor if ascending else AuditPublication.id < cursor
        )
    order = (AuditPublication.id.asc(),) if ascending else (AuditPublication.id.desc(),)
    if export:
        order = (AuditEvent.created_at.asc(), AuditEvent.id.asc())
    return list(
        (
            await session.execute(
                statement.order_by(*order).limit(10001 if export else query.page_size + 1)
            )
        ).all()
    )


async def profile_for_user(session, user):
    model = StudentProfile if user.user_type == UserType.STUDENT else TeacherProfile
    return await session.get(model, user.id)


async def publish_audit_batch(session):
    """有限补齐已提交事件；发布锁内分配序号，事务延迟提交的事件留待下一批。"""
    await session.get(AuditPublicationState, 1, with_for_update=True)
    pending = list(
        (
            await session.execute(
                select(AuditEvent.id, AuditPublication.id)
                .outerjoin(AuditPublication, AuditPublication.event_id == AuditEvent.id)
                # 与部分索引谓词保持 NOT boolean 等价形式，IS FALSE 无法匹配该索引。
                .where(~AuditEvent.log_published)
                .order_by(AuditEvent.created_at, AuditEvent.id)
                .limit(1000)
            )
        ).all()
    )
    # 支持迁移期间旧进程仍发布而未写新标记，不能重复插入已有投影。
    ids = [identifier for identifier, _ in pending]
    session.add_all(
        AuditPublication(event_id=identifier)
        for identifier, publication_id in pending
        if publication_id is None
    )
    await session.flush()
    if ids:
        await session.execute(
            update(AuditEvent).where(AuditEvent.id.in_(ids)).values(log_published=True)
        )
    return len(ids)


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
