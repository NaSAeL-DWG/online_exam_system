from sqlalchemy import func, or_, select
from .models import Question


async def insert(session, item):
    session.add(item)
    await session.flush()


async def by_id(session, question_id, *, lock=False):
    return await session.get(Question, question_id, with_for_update=lock, populate_existing=lock)


async def list_page(session, pagination, filters):
    statement = select(Question)
    for key, value in filters.items():
        if value is not None:
            statement = statement.where(
                Question.knowledge_tags.contains([value])
                if key == "tag"
                else getattr(Question, key) == value
            )
    if pagination.q.strip():
        term = "%" + pagination.q.strip() + "%"
        statement = statement.where(or_(Question.content.ilike(term), Question.subject.ilike(term)))
    total = await session.scalar(select(func.count()).select_from(statement.subquery()))
    rows = (
        await session.scalars(
            statement.order_by(Question.created_at.desc(), Question.id)
            .offset((pagination.page - 1) * pagination.page_size)
            .limit(pagination.page_size)
        )
    ).all()
    return rows, total


async def locked_many(session, ids):
    # 按固定顺序一次锁定全部来源，复制时不会混入同题的新旧版本。
    return (
        await session.scalars(
            select(Question)
            .where(Question.id.in_(ids))
            .order_by(Question.id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
    ).all()
