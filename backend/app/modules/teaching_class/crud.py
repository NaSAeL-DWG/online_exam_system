from sqlalchemy import delete, func, or_, select

from .models import ClassMember, MemberRole, TeachingClass


async def by_id(session, class_id, *, lock=False):
    return await session.get(TeachingClass, class_id, with_for_update=lock, populate_existing=lock)


async def member(session, class_id, user_id):
    return await session.get(ClassMember, (class_id, user_id))


async def members(session, class_ids, *, teachers_only=False):
    statement = select(ClassMember).where(ClassMember.class_id.in_(class_ids))
    if teachers_only:
        statement = statement.where(ClassMember.role == MemberRole.TEACHER)
    return (
        await session.scalars(statement.order_by(ClassMember.class_id, ClassMember.user_id))
    ).all()


async def list_page(session, pagination, teacher_id=None):
    statement = select(TeachingClass)
    if teacher_id:
        statement = statement.join(ClassMember).where(
            ClassMember.user_id == teacher_id, ClassMember.role == MemberRole.TEACHER
        )
    if pagination.q.strip():
        term = "%" + pagination.q.strip() + "%"
        statement = statement.where(
            or_(TeachingClass.name.ilike(term), TeachingClass.description.ilike(term))
        )
    total = await session.scalar(select(func.count()).select_from(statement.subquery()))
    rows = (
        await session.scalars(
            statement.order_by(TeachingClass.created_at.desc(), TeachingClass.id)
            .offset((pagination.page - 1) * pagination.page_size)
            .limit(pagination.page_size)
        )
    ).all()
    return rows, total


async def student_counts(session, class_ids):
    rows = (
        await session.execute(
            select(ClassMember.class_id, func.count())
            .where(ClassMember.class_id.in_(class_ids), ClassMember.role == MemberRole.STUDENT)
            .group_by(ClassMember.class_id)
        )
    ).all()
    return dict(rows)


async def add_class(session, item):
    session.add(item)
    await session.flush()


async def replace_teachers(session, class_id, teacher_ids):
    await session.execute(
        delete(ClassMember).where(
            ClassMember.class_id == class_id, ClassMember.role == MemberRole.TEACHER
        )
    )
    session.add_all(
        [
            ClassMember(class_id=class_id, user_id=user_id, role=MemberRole.TEACHER)
            for user_id in teacher_ids
        ]
    )
    await session.flush()


async def put_member(session, class_id, user_id, role):
    existing = await member(session, class_id, user_id)
    if existing:
        existing.role = role
    else:
        session.add(ClassMember(class_id=class_id, user_id=user_id, role=role))
    await session.flush()


async def remove_member(session, item):
    await session.delete(item)
