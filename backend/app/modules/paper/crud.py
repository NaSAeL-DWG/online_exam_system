from sqlalchemy import func, select

from .models import Paper, PaperQuestion


async def by_id(session, paper_id, *, lock=False):
    return await session.get(Paper, paper_id, with_for_update=lock, populate_existing=lock)


async def insert(session, item):
    session.add(item)
    await session.flush()


async def items(session, paper_ids):
    return (
        await session.scalars(
            select(PaperQuestion)
            .where(PaperQuestion.paper_id.in_(paper_ids))
            .order_by(PaperQuestion.paper_id, PaperQuestion.order_no)
        )
    ).all()


async def synchronize_items(session, paper_id, values):
    existing = {item.question_id: item for item in await items(session, [paper_id])}
    desired = {value.question_id for value in values}
    for question_id, item in existing.items():
        if question_id not in desired:
            await session.delete(item)
    for order_no, value in enumerate(values, 1):
        item = existing.get(value.question_id)
        if item is None:
            item = PaperQuestion(
                paper_id=paper_id,
                question_id=value.question_id,
                order_no=order_no,
                score=value.score,
            )
            session.add(item)
        else:
            item.order_no = order_no
            item.score = value.score
    await session.flush()


async def list_page(session, pagination, status):
    statement = select(Paper)
    if pagination.q.strip():
        statement = statement.where(Paper.title.ilike("%" + pagination.q.strip() + "%"))
    if status is not None:
        statement = statement.where(Paper.status == status)
    total = await session.scalar(select(func.count()).select_from(statement.subquery()))
    rows = (
        await session.scalars(
            statement.order_by(Paper.created_at.desc(), Paper.id)
            .offset((pagination.page - 1) * pagination.page_size)
            .limit(pagination.page_size)
        )
    ).all()
    aggregates = (
        (
            await session.execute(
                select(PaperQuestion.paper_id, func.count(), func.sum(PaperQuestion.score))
                .where(PaperQuestion.paper_id.in_([row.id for row in rows]))
                .group_by(PaperQuestion.paper_id)
            )
        ).all()
        if rows
        else []
    )
    return rows, total, {row[0]: (row[1], row[2]) for row in aggregates}
